"""同机多实例的 PID 隔离（BUG-2）

【覆盖的语义】
1. `iwan core stop` 只能杀**本端口**上的 daemon；另一份副本的 daemon 必须活着
2. `iwan core status` 只报目标端口上的实例（有本实例 PID 记录时带 pid）
3. 重复 stop 幂等：第二次打印 `not running`，不报错、不误杀
4. PID 记录带端口，端口对不上时一律判"未运行"（宁可不动手，也不杀别人的进程）
5. 兼容旧的纯数字 PID 文件（升级路径不能因为格式变化就丢状态）
6. 懒启动路径（daemon_guard）的默认 PID 文件同样按端口区分

【为什么这些用例能抓住 BUG-2】
旧实现用用户级共享路径 `~/.iwan/iwan-core.pid`，`_running_pid()` 也不校验端口：
后启动的副本覆盖记录后，任意一份 `core stop` 都会按"别人的 PID"去 taskkill。
下面第 2 组用例模拟"两份副本各有记录"，断言只杀自己那条。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from iwan_claude.cli import daemon_guard
from iwan_claude.cli.commands import core as core_cmd
from iwan_claude.core.config import IwanConfig

# --- helpers -----------------------------------------------------------------


def _cfg(port: int) -> IwanConfig:
    return IwanConfig(host="127.0.0.1", port=port)


@pytest.fixture
def pid_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 PID 目录改道到 tmp，任何用例都不会碰用户真实 ~/.iwan"""
    target = tmp_path / "pids"
    monkeypatch.setattr(core_cmd, "_PID_DIR", target)
    monkeypatch.delenv("IWAN_PID_FILE", raising=False)
    return target


class _KillRecorder:
    """记录被 kill 的 PID，避免真的去 taskkill"""

    def __init__(self) -> None:
        self.killed: list[int] = []

    def __call__(self, pid: int) -> None:
        self.killed.append(pid)


@pytest.fixture
def kill_recorder(monkeypatch: pytest.MonkeyPatch) -> _KillRecorder:
    rec = _KillRecorder()
    monkeypatch.setattr(core_cmd, "_kill_pid", rec)
    # 本用例里写入的 pid 一律当作"存活"，否则 stop 会先清脏文件直接返回
    monkeypatch.setattr(core_cmd, "_pid_alive", lambda pid: pid in (1111, 2222, os.getpid()))
    return rec


# --- 1. PID 文件按端口隔离 ---------------------------------------------------


# 功能：两个端口解析出两个不同的 PID 文件，且路径里带端口号
# 设计：只断言"不同"不够——如果实现退化成随机名，也满足"不同"但失去可诊断性，
#       所以同时断言端口号出现在文件名里
def test_pid_file_is_per_port(pid_dir: Path) -> None:
    a = core_cmd._pid_file(_cfg(7438))
    b = core_cmd._pid_file(_cfg(7439))
    assert a != b
    assert "7438" in a.name and "7439" in b.name
    assert a.parent == pid_dir


# 功能：IWAN_PID_FILE 显式指定时优先（测试/高级用法）
# 设计：这条同时保证"临时改道"能力不会被按端口的默认路径破坏
def test_pid_file_honours_env_override(
    pid_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "custom.pid"
    monkeypatch.setenv("IWAN_PID_FILE", str(custom))
    assert core_cmd._pid_file(_cfg(7438)) == custom


# --- 2. stop 只杀自己（BUG-2 主判据） ---------------------------------------


# 功能：7438 的 stop 不动 7439 的 daemon
# 设计：两份副本各写一条带端口的记录，只对 7438 执行 stop，断言
#       ①只杀了 1111 ②7439 的记录文件还在（别人的状态不能被清掉）
def test_stop_only_kills_own_instance(
    pid_dir: Path, kill_recorder: _KillRecorder
) -> None:
    cfg_a, cfg_b = _cfg(7438), _cfg(7439)
    core_cmd._write_pid_record(core_cmd._pid_file(cfg_a), 1111, cfg_a)
    core_cmd._write_pid_record(core_cmd._pid_file(cfg_b), 2222, cfg_b)

    core_cmd.cmd_core_stop(cfg_a)

    assert kill_recorder.killed == [1111]
    assert not core_cmd._pid_file(cfg_a).exists()
    assert core_cmd._pid_file(cfg_b).exists(), "另一个实例的 PID 记录不该被删"
    assert json.loads(core_cmd._pid_file(cfg_b).read_text(encoding="utf-8"))["pid"] == 2222


# 功能：重复 stop 幂等（第二次打印 not running，不再杀进程）
# 设计：幂等是 BUG-2 验收标准第 1 条明确要求的；只测第一次会漏掉擦除后的行为
def test_stop_is_idempotent(
    pid_dir: Path, kill_recorder: _KillRecorder, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _cfg(7438)
    core_cmd._write_pid_record(core_cmd._pid_file(cfg), 1111, cfg)

    core_cmd.cmd_core_stop(cfg)
    first = capsys.readouterr().out
    core_cmd.cmd_core_stop(cfg)
    second = capsys.readouterr().out

    assert "stopped" in first
    assert "not running" in second
    assert kill_recorder.killed == [1111]


# 功能：PID 记录里的端口与当前配置不一致时，一律判"未运行"且不动进程
# 设计：这是"共享 PID 文件"时代的真实风险场景（用户把 IWAN_PID_FILE 指到同一个文件），
#       断言不杀进程比断言返回 None 更重要
def test_stop_refuses_record_from_other_port(
    pid_dir: Path, tmp_path: Path, kill_recorder: _KillRecorder,
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = tmp_path / "shared.pid"
    monkeypatch.setenv("IWAN_PID_FILE", str(shared))
    other = _cfg(7439)
    core_cmd._write_pid_record(shared, 2222, other)

    core_cmd.cmd_core_stop(_cfg(7438))

    assert "not running" in capsys.readouterr().out
    assert kill_recorder.killed == []
    assert shared.exists(), "别人实例的记录不能被当脏文件删掉"


# 功能：进程已消失的脏记录会被清理，并判为未运行
# 设计：脏文件清理是 stop/status 的常规路径，只修"按端口分文件"不覆盖它
def test_stale_pid_record_is_cleaned(
    pid_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(core_cmd, "_pid_alive", lambda pid: False)
    cfg = _cfg(7438)
    path = core_cmd._pid_file(cfg)
    core_cmd._write_pid_record(path, 3333, cfg)

    assert core_cmd._running_pid(cfg) is None
    assert not path.exists()
    core_cmd.cmd_core_stop(cfg)
    assert "not running" in capsys.readouterr().out


# --- 3. status 只报目标端口 --------------------------------------------------


# 功能：status 打印目标端口与 pid
# 设计：BUG-2 验收第 2 条要求 status 只报目标端口的实例；把 pid 打出来才能让
#       用户当场分辨"这是我刚起的 daemon，还是别人的"
def test_status_reports_target_port_and_pid(
    pid_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _cfg(7438)
    core_cmd._write_pid_record(core_cmd._pid_file(cfg), 1111, cfg)

    async def _ok(_config: IwanConfig) -> None:
        return None

    monkeypatch.setattr(core_cmd, "_ping_check", _ok)
    monkeypatch.setattr(core_cmd, "_pid_alive", lambda pid: pid == 1111)
    core_cmd.cmd_core_status(cfg)

    out = capsys.readouterr().out
    assert "7438" in out
    assert "pid=1111" in out


# 功能：端口活着但没有本实例记录时，status 报 pid=?（外部实例）
# 设计：懒启动/手动 `-m iwan_claude.core` 起的 daemon 不写 core 的 PID 文件，
#       这时不能假装知道 pid，也不能因此报"not running"
def test_status_reports_unknown_pid_for_foreign_instance(
    pid_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def _ok(_config: IwanConfig) -> None:
        return None

    monkeypatch.setattr(core_cmd, "_ping_check", _ok)
    core_cmd.cmd_core_status(_cfg(7439))
    out = capsys.readouterr().out
    assert "7439" in out and "pid=?" in out


# --- 4. 兼容旧格式 + 懒启动路径 ----------------------------------------------


# 功能：旧版纯数字 PID 文件仍可读（升级不丢状态）
# 设计：兼容层是 BUG-2 修复的迁移风险点：老用户 ~/.iwan 下可能还留着纯数字文件
def test_legacy_plain_int_pid_file_is_supported(pid_dir: Path) -> None:
    path = pid_dir / "legacy.pid"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("4321", encoding="utf-8")
    record = core_cmd._read_pid_record(path)
    assert record is not None and record["pid"] == 4321


# 功能：内容非法的 PID 文件不会抛异常，按"未运行"处理
# 设计：脏文件容错是 pid 管理的底线（半写入、被占用、权限不足都会留下坏内容）
def test_corrupt_pid_file_is_ignored(pid_dir: Path) -> None:
    path = pid_dir / "corrupt.pid"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert core_cmd._read_pid_record(path) is None


# 功能：懒启动用的默认 PID 文件也按端口区分
# 设计：core 命令与 daemon_guard 是两条独立路径，只修一条仍会出现
#       "stop 杀了懒启动的实例"或反之；这里锁住 daemon_guard 的默认路径
def test_daemon_guard_default_pid_is_per_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IWAN_PID_FILE", raising=False)
    a = daemon_guard._resolve_pid_path(7438)
    b = daemon_guard._resolve_pid_path(7439)
    assert a != b
    assert "7438" in a.name and "7439" in b.name


# 功能：IWAN_PID_FILE 与测试里 monkeypatch 的固定路径都不带 {port} 占位符时不崩
# 设计：现有 test_daemon_guard.py 就是这么覆盖默认路径的，格式化必须容错
def test_daemon_guard_pid_path_without_placeholder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("IWAN_PID_FILE", raising=False)
    fixed = tmp_path / "daemon.pid"
    monkeypatch.setattr(daemon_guard, "_DEFAULT_PID_FILE", str(fixed))
    assert daemon_guard._resolve_pid_path(7438) == fixed

    monkeypatch.setenv("IWAN_PID_FILE", str(tmp_path / "env.pid"))
    assert daemon_guard._resolve_pid_path(7439) == tmp_path / "env.pid"


# 功能：ensure_daemon 不传 pid_file 时使用按端口的默认路径
# 设计：只测 _resolve_pid_path 还不够——真正决定锁文件位置的是 ensure_daemon
#       内部那次解析；用注入的 connect_fn 让它走"已就绪"的最快路径
def test_ensure_daemon_uses_per_port_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("IWAN_PID_FILE", raising=False)
    monkeypatch.setattr(daemon_guard, "_DEFAULT_PID_FILE", str(tmp_path / "d-{port}.pid"))
    calls: list[tuple[str, int]] = []

    def _connect(host: str, port: int) -> bool:
        calls.append((host, port))
        return True

    assert daemon_guard.ensure_daemon(_cfg(7439), connect_fn=_connect) is True
    assert calls == [("127.0.0.1", 7439)]
    # 已就绪的最快路径不会创建 PID 文件，这里只验证解析没报错
    assert not (tmp_path / "d-7439.pid").exists()


# 功能：_write_pid_record 落盘内容包含端口与启动时间（供人工排查）
# 设计：字段缺失会让"误杀排查"退化成猜——端口是判定归属的唯一依据，必须落盘
def test_pid_record_contains_port_and_start_time(pid_dir: Path) -> None:
    cfg = _cfg(7438)
    path = core_cmd._pid_file(cfg)
    core_cmd._write_pid_record(path, 1111, cfg)
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    assert data["pid"] == 1111
    assert data["port"] == 7438
    assert data["host"] == "127.0.0.1"
    assert data["started_at"]
