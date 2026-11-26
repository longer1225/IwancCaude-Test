"""
核心服务管理命令模块 - 管理 daemon 的启动、停止和状态查询

【学习要点】
1. 进程管理：如何检测进程是否存在、如何终止进程
2. 跨平台兼容性：Windows 和 Unix 系统的进程管理方式不同
3. PID 文件：用于记录后台进程的 PID，实现进程状态追踪
4. 后台进程启动：使用 subprocess.Popen 创建独立于终端的进程
5. 守护进程模式：在 Unix 上使用 start_new_session，在 Windows 上使用 CREATE_NEW_PROCESS_GROUP

【核心概念】
- Daemon：在后台运行的服务进程，不依附于终端
- PID：进程标识符，每个运行中的进程都有唯一的 PID
- PID 文件：存储 PID 的文件，用于追踪后台进程
"""
from __future__ import annotations

# asyncio：用于异步网络连接测试
# os：操作系统相关功能，如进程管理
# signal：信号处理，用于 Unix 系统的进程终止
# subprocess：创建子进程，用于启动 daemon 和执行系统命令
# sys：系统相关操作，如获取 Python 解释器路径、判断操作系统
# pathlib：路径操作，用于文件和目录管理
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# 导入配置数据结构
from iwan_claude.core.config import IwanConfig

log = logging.getLogger(__name__)

# PID 文件目录：**按实例（端口）分文件**
# 【为什么不再用 ~/.iwan/iwan-core.pid】那是用户级共享路径：同机跑两份副本
# （7438/7439）时，后启动的会把前一份的记录覆盖掉，于是任意一份执行
# `iwan core stop` 都可能按"别人的 PID"去杀进程（BUG-2）。
_PID_DIR = Path.home() / ".iwan" / "pids"

# 平台兼容性判断：检查当前操作系统是否为 Windows
IS_WINDOWS = sys.platform == "win32"


# 当前实例的 PID 文件路径（按端口区分，可用 IWAN_PID_FILE 显式指定）
def _pid_file(config: IwanConfig) -> Path:
    """
    返回当前实例的 PID 文件路径

    【优先级】IWAN_PID_FILE（显式指定，测试/高级用法） >
              ~/.iwan/pids/iwan-core-<port>.pid

    参数：
        config: IwanConfig 配置对象（只用 host/port）

    返回值：
        Path: 该实例独占的 PID 文件路径
    """
    override = os.environ.get("IWAN_PID_FILE")
    if override:
        return Path(override).expanduser()
    return _PID_DIR / f"iwan-core-{config.port}.pid"


# 读 PID 记录：新格式是 JSON（含端口/启动时间），兼容旧的纯数字文件
def _read_pid_record(path: Path) -> dict[str, Any] | None:
    """
    读取 PID 记录文件

    参数：
        path: PID 文件路径

    返回值：
        dict | None: 至少含 "pid" 键；文件不存在/内容非法时返回 None

    【兼容性】旧版本写的是纯数字。这里仍然接受，只是拿不到端口字段——
    调用方按"无端口信息"处理（也就是只校验进程存活）。
    """
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        try:
            return {"pid": int(text)}
        except ValueError:
            return None
    # 纯数字在 JSON 里是合法标量（"4321" 会被解析成 int），同样按旧格式接受
    if isinstance(obj, int):
        return {"pid": obj}
    if not isinstance(obj, dict):
        return None
    try:
        obj["pid"] = int(obj["pid"])
    except (KeyError, TypeError, ValueError):
        return None
    return obj


# 写 PID 记录：pid + 端口 + 启动时间 + 工作目录
def _write_pid_record(path: Path, pid: int, config: IwanConfig) -> None:
    """
    写入 PID 记录（JSON）

    参数：
        path: PID 文件路径
        pid: daemon 进程号
        config: IwanConfig 配置对象

    【为什么要记端口和启动时间】Windows 的 PID 会被复用，只比对数字不可靠；
    端口用于确认"这条记录属于哪个实例"，启动时间用于事后排查。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "host": config.host,
        "port": config.port,
        "started_at": datetime.now(UTC).isoformat(),
        "cwd": str(Path.cwd()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# 尝试连接 daemon，成功则正常返回，失败则抛出异常
async def _ping_check(config: IwanConfig) -> None:
    """
    检查 daemon 是否正在运行
    
    通过尝试建立 TCP 连接来检测 daemon 是否存活
    如果连接成功，说明 daemon 正在运行；如果连接被拒绝，说明未运行
    
    参数：
        config: IwanConfig 配置对象，包含 host 和 port 信息
    
    异常：
        ConnectionRefusedError: 连接被拒绝（daemon 未运行）
        OSError: 其他网络错误
    """
    # 创建 TCP 连接，不发送任何数据
    _r, w = await asyncio.open_connection(config.host, config.port)
    # 立即关闭连接
    w.close()
    await w.wait_closed()


# 跨平台：检查指定 PID 的进程是否存在
def _pid_alive(pid: int) -> bool:
    """
    判断给定 PID 的进程是否仍然存活
    
    跨平台实现：
    - Windows：使用 tasklist 命令查询进程
    - Unix：使用 os.kill(pid, 0) 发送空信号（不终止进程，只检查存在性）
    
    参数：
        pid: 进程标识符
    
    返回：
        bool: 进程存在返回 True，否则返回 False
    """
    if IS_WINDOWS:
        # Windows：使用 tasklist 命令过滤指定 PID
        # /FI 是 filter 参数，PID eq {pid} 表示只显示 PID 等于指定值的进程
        # /NH 表示不显示表头（No Header）
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,  # 捕获 stdout 和 stderr
                text=True,            # 返回文本而非字节
                timeout=5,            # 5 秒超时
            )
            # 如果 PID 在输出中，说明进程存在
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        # Unix：os.kill(pid, 0) 发送信号 0，不终止进程，只做存在性检查
        # 如果进程不存在，会抛出 ProcessLookupError
        # 如果没有权限，会抛出 PermissionError
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


# 读取本实例的 PID 记录并确认进程存活，进程已消失则删除文件并返回 None
def _running_pid(config: IwanConfig) -> int | None:
    """
    获取当前实例运行中的 daemon 进程 PID

    工作流程：
    1. 定位本实例的 PID 文件（按端口）
    2. 读取记录，校验记录里的端口与当前配置一致
    3. 验证进程是否仍然存活
    4. 如果进程不存在，删除脏 PID 文件

    参数：
        config: IwanConfig 配置对象

    返回：
        int | None: 进程 PID，如果未运行/不是本实例/文件不存在返回 None

    【为什么不直接杀文件里的 PID】旧实现读的是共享文件，文件里那条记录可能属于
    另一个端口上的实例。端口不一致时宁可判"未运行"，也不能去杀别人的进程。
    """
    path = _pid_file(config)
    record = _read_pid_record(path)
    if record is None:
        return None

    # 显式窄化类型：记录来自 JSON，字典取值是 Any（mypy strict 下不能直传）
    pid = int(record["pid"])
    recorded_port = record.get("port")
    if recorded_port is not None:
        try:
            if int(recorded_port) != config.port:
                log.debug(
                    "pid file %s belongs to port %s, not %s — ignore",
                    path, recorded_port, config.port,
                )
                return None
        except (TypeError, ValueError):
            return None

    # 检查进程是否存活
    if _pid_alive(pid):
        return pid

    # 进程已消失，但 PID 文件还在（脏文件），删除它
    path.unlink(missing_ok=True)
    return None


# 跨平台：终止指定 PID 的进程
def _kill_pid(pid: int) -> None:
    """
    终止指定 PID 的进程
    
    跨平台实现：
    - Windows：使用 taskkill /F /PID 强制终止进程
    - Unix：发送 SIGTERM 信号，优雅终止进程
    
    参数：
        pid: 要终止的进程 PID
    """
    if IS_WINDOWS:
        # Windows：taskkill 命令终止进程
        # /F 表示强制终止（Force）
        # /PID 指定要终止的进程 PID
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            timeout=5,
        )
    else:
        # Unix：发送 SIGTERM 信号
        # SIGTERM 是终止信号，进程可以捕获并进行清理工作
        os.kill(pid, signal.SIGTERM)


# 打印 daemon 当前状态（running / not running）
def cmd_core_status(config: IwanConfig) -> None:
    """
    显示 daemon 的运行状态
    
    使用方式：iwan core status
    
    参数：
        config: IwanConfig 配置对象
    
    输出：
        running (host:port) 或 not running
    """
    try:
        # 尝试连接 daemon
        asyncio.run(_ping_check(config))
        # 连接成功：能连上的只可能是这个端口上的实例
        pid = _running_pid(config)
        if pid is not None:
            print(f"running  ({config.host}:{config.port})  pid={pid}")
        else:
            # 端口活着但没有本实例的记录：别的入口起的（懒启动/手动 -m）
            print(f"running  ({config.host}:{config.port})  pid=?")
    except (ConnectionRefusedError, OSError):
        # 连接失败，打印未运行状态
        print("not running")


# 在后台启动 daemon，若已在运行则提示并退出
def cmd_core_start(config: IwanConfig) -> None:
    """
    在后台启动 daemon 进程

    使用方式：iwan core start

    工作流程：
    1. 检查 daemon 是否已运行
    2. 获取当前工作目录（作为初始 CWD）
    3. 创建后台进程
    4. 将 PID 写入 PID 文件
    5. 打印启动信息

    【关于 CWD 和沙箱根】
    - daemon 的 CWD = 当前工作目录（启动时所在的目录）
    - 每个会话的沙箱根由 TUI 创建会话时传入的 cwd 参数控制
    - 会话 cwd 会覆盖 daemon 的初始 CWD，实现多项目隔离
    - 详见 SessionManager.create() 和 SandboxManager.set_root()

    参数：
        config: IwanConfig 配置对象
    """
    try:
        # 先检查 daemon 是否已运行
        asyncio.run(_ping_check(config))
        print(f"already running  ({config.host}:{config.port})")
        return
    except (ConnectionRefusedError, OSError):
        # 未运行，继续启动流程
        pass

    # 获取当前工作目录作为 daemon 的初始 CWD
    # 会话创建时会通过 cwd 参数覆盖沙箱根
    current_cwd = Path.cwd()

    # 后台进程参数
    popen_kwargs: dict[str, Any] = dict(
        stdout=subprocess.DEVNULL,  # 标准输出重定向到空设备（丢弃）
        stderr=subprocess.DEVNULL,  # 标准错误重定向到空设备（丢弃）
        cwd=str(current_cwd),       # 设置子进程的工作目录为当前目录
    )
    
    if IS_WINDOWS:
        # Windows：使用 CREATE_NEW_PROCESS_GROUP 创建独立进程组
        # 这样进程不会继承父进程的控制台，关闭控制台不会终止 daemon
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Unix：使用 start_new_session 创建新会话
        # 这样 daemon 进程与当前终端完全脱离，成为独立的会话领导者
        popen_kwargs["start_new_session"] = True

    # 创建子进程，运行 iwan_claude.core 模块
    # sys.executable 是当前 Python 解释器的路径
    # -m 参数表示运行模块
    proc = subprocess.Popen(
        [sys.executable, "-m", "iwan_claude.core"],
        **popen_kwargs,
    )
    
    # 确保本实例 PID 文件的父目录存在，并写入带端口信息的记录
    _write_pid_record(_pid_file(config), proc.pid, config)
    
    # 打印启动信息
    print(f"started  pid={proc.pid}  ({config.host}:{config.port})")
    print(f"  cwd: {current_cwd}")


# 终止 daemon 进程，若未运行则提示
def cmd_core_stop(config: IwanConfig) -> None:
    """
    停止 daemon 进程
    
    使用方式：iwan core stop
    
    工作流程：
    1. 读取 PID 文件获取进程 PID
    2. 如果未运行，打印提示并返回
    3. 终止进程
    4. 删除 PID 文件
    5. 打印停止信息
    
    参数：
        config: IwanConfig 配置对象
    """
    # 获取本实例运行中的进程 PID
    pid = _running_pid(config)
    
    if pid is None:
        # 未运行，打印提示
        print("not running")
        return
    
    # 终止进程
    _kill_pid(pid)
    # 删除本实例的 PID 文件（别人的文件不碰）
    _pid_file(config).unlink(missing_ok=True)
    # 打印停止信息
    print(f"stopped  pid={pid}")
