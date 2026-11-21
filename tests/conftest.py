from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest

try:  # tests 是包时按包名导入；直接跑单文件时退回同级模块
    from tests.tmp_utils import test_tmp_root
except ImportError:  # pragma: no cover - 仅在非包模式下走到
    from tmp_utils import test_tmp_root


@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return port  # socket released; daemon can bind to this port


# 关掉 Windows 注册表环境变量兜底（core/win_env.py）：开发机的真实 DEEPSEEK_API_KEY
# 藏在用户/系统环境变量里，兜底会让"缺 key 应当报错"的用例在开发机上静默变成"有 key"
os.environ["IWAN_DISABLE_WIN_ENV_FALLBACK"] = "1"
# 包根 .env 的兜底路径指到不存在的文件：开发机 .env 里的 IWAN_PORT / 密钥不得渗进单测
# （只影响"当前目录没有 .env 时回落到包根"这条路；用例自己在 cwd 写 .env 的行为不变）
os.environ["IWAN_ENV_FILE"] = str(test_tmp_root() / "no-such.env")


# 本机密钥文件全量改道：开发机上真有一把 ~/.iwan/secrets.env 时，任何 import 期
# get_config() 都会把真 key 注进测试进程环境——"缺 key 应当报错"的断言会静默失效，
# 更糟的是 running_daemon 复制 os.environ 后集成测试可能真打到线上 API
@pytest.fixture(scope="session", autouse=True)
def _isolate_secrets_file() -> Generator[None, None, None]:
    previous = os.environ.get("IWAN_SECRETS_FILE")
    os.environ["IWAN_SECRETS_FILE"] = str(test_tmp_root() / "secrets-isolated.env")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("IWAN_SECRETS_FILE", None)
        else:
            os.environ["IWAN_SECRETS_FILE"] = previous


@pytest.fixture
def daemon_env() -> dict[str, str]:
    # 用例级 fixture：返回要追加进 daemon 子进程的环境变量（默认空）
    return {}


@pytest.fixture
async def running_daemon(
    free_port: int, daemon_env: dict[str, str], request: pytest.FixtureRequest
) -> AsyncGenerator[subprocess.Popen[bytes], None]:
    # 临时目录统一落在 runs/tmp（系统 temp 不可写时 tempfile 会退回 cwd，把仓库根弄脏）
    tmp_dir = Path(tempfile.mkdtemp(prefix="iwan_daemon_", dir=test_tmp_root()))
    # 【学习要点】finalizer 必须在建目录后立刻注册：daemon 启动失败时会在 yield 之前
    # pytest.fail，写在 yield 之后的清理代码不会执行——那正是仓库根堆满临时目录的原因
    request.addfinalizer(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
    env = os.environ.copy()
    env["IWAN_PORT"] = str(free_port)
    env["IWAN_LOG_FILE"] = ""
    # 测试 daemon 恒为免鉴权：用户 shell 里残留的 IWAN_TOKEN 不得泄进测试实例
    env["IWAN_TOKEN"] = ""
    # 同理隔离 GitHub 令牌：测试 daemon 的 cwd 是仓库根，会自动加载 .env 里的真实
    # IWAN_GITHUB_TOKEN——一旦带上它，连"非 git/匿名"类负向用例都可能因真拉到 PR 而翻红。
    # 配置层 IWAN_GITHUB_TOKEN 用 `is not None` 判定，故显式设空即可盖过 .env 的值。
    env["IWAN_GITHUB_TOKEN"] = ""
    env["IWAN_LOG_LEVEL"] = "WARNING"
    # 家目录写入全部改道 tmp：受限环境（workspace-write 沙箱 / Win 服务账号）里 daemon
    # 启动期往 ~/.iwan/traces 或 ~/.iwan_claude/memory mkdir 会直接 PermissionError
    env["IWAN_TRACE_FILE"] = str(tmp_dir / "traces" / "daemon.jsonl")
    env["IWAN_MEMORY_DIR"] = str(tmp_dir / "memory")
    env["IWAN_SESSIONS_DIR"] = str(tmp_dir / "sessions")
    env["IWAN_POLICY_FILE"] = str(tmp_dir / "policy.toml")
    # 本机密钥文件也改道 tmp：否则 daemon 会读到开发机真实 key，集成测试变成线上调用
    env["IWAN_SECRETS_FILE"] = str(tmp_dir / "secrets.env")
    # 信任文件同样关进 tmp：否则 daemon 会读用户真实 ~/.iwan/trust.toml，
    # 目录被标成 deny/allow 时信任相关用例会随机翻红（也与"测试不碰用户数据"冲突）
    env["IWAN_TRUST_FILE"] = str(tmp_dir / "trust.toml")
    # 插件安装目录与账本一起改道临时目录：集成测试的 set_enabled 绝不写用户 ~/.iwan
    env["IWAN_PLUGINS_DIR"] = str(tmp_dir / "plugins")
    # 关语音预热：测试 daemon 不拖百兆模型进内存、不依赖模型缓存存在
    env["IWAN_SPEECH_PREWARM"] = "0"
    # 注册表兜底同样要关：否则子 daemon 会从用户/系统环境变量里捞到真 key
    env["IWAN_DISABLE_WIN_ENV_FALLBACK"] = "1"
    # LLM：daemon 启动期就会构造 provider（会话摘要用），缺 key 直接 SystemExit
    # ——不注入假 key 的话，整套集成测试都会死在 "Daemon did not start"。
    # 没有真实 key 的环境用假 key + 死端口 base_url：daemon 能起，万一有用例触发
    # run 也会立刻 llm_error（不联网、不烧 token）；有真 key 的环境保持原样。
    if not (env.get("DEEPSEEK_API_KEY") or env.get("ANTHROPIC_API_KEY")):
        env["DEEPSEEK_API_KEY"] = "test-key-not-validated"
        env["IWAN_LLM_BASE_URL"] = "http://127.0.0.1:9"
    # 用例级覆盖（例如信任闸门用例要把信任超时压短）
    env.update(daemon_env)

    # 启动 daemon 子进程，将 stderr 重定向到临时日志以便排查启动失败
    stderr_path = tmp_dir / "daemon_stderr.log"
    stderr_fh = open(stderr_path, "w", encoding="utf-8")
    # Windows 上目录里有打开的文件就删不掉：句柄的清理必须排在校验失败删目录之前
    # （finalizer 是 LIFO，所以这里先注册 rmtree、再注册 close 即可）
    request.addfinalizer(stderr_fh.close)
    proc = subprocess.Popen(
        [sys.executable, "-m", "iwan_claude.core"],
        env=env,
        stderr=stderr_fh,
    )

    # 首次冷启动需要编译字节码并加载持久化策略，超时放宽到 10 秒
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        try:
            _reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
            writer.close()
            await writer.wait_closed()
            break
        except (ConnectionRefusedError, OSError):
            pass
    else:
        proc.terminate()
        proc.wait()
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="ignore") if stderr_path.exists() else ""
        pytest.fail(f"Daemon did not start within 10 seconds\nstderr:\n{stderr_text}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    # 目录由上面的 finalizer 统一删，这里不再重复


# 会话级兜底：清掉测试临时根里剩下的空壳目录（失败用例的 finalizer 可能因文件占用失败）
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(test_tmp_root(), ignore_errors=True)
