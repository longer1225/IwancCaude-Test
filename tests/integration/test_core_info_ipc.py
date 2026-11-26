"""core.info 的 RPC 语义（BUG-3 的服务端半边）

【覆盖的语义】
1. `core.info` 返回 daemon 自己的 cwd / 仓库根 / 配置路径 / 监听端口
2. 响应字段集合固定：只读路径与版本，不含任何密钥/令牌字段
3. `core.ping` 只给版本与运行时间，区分不出仓库——所以单开一条命令，而不是改 ping
   （改 ping 的返回结构会破坏所有老客户端的解析）

【和 GUI 的分工】
服务端只负责"如实报告我是谁"。GUI 侧拿 `repo_root` 与本地 `findRepoRoot()` 比较、
不一致就提示"已连接外部 daemon（路径）"。"仓库根向上查找"的语义由
`tests/unit/test_core_info_repo_root.py` 单测覆盖，这里只验证 RPC 通道与字段契约。

【为什么做成集成测试】这条命令的价值在"跨进程"：只有真的起一个 daemon 子进程，
才能验证它报的是**那个进程**的 cwd，而不是测试进程的。
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from iwan_claude.core.transport.socket_client import SocketClient


async def _connect(port: int) -> tuple[SocketClient, asyncio.Task[None]]:
    client = SocketClient("127.0.0.1", port)
    await client.connect()
    task = asyncio.create_task(client.run_event_loop())
    return client, task


# 功能：core.info 报出本实例的 cwd / 仓库根 / 配置路径 / 端口
# 设计：断言"仓库根里有 pyproject.toml 与 src/iwan_claude"——比断言绝对路径更稳
#       （换成别的机器/别的副本目录也成立）
async def test_core_info_reports_instance_identity(
    running_daemon: subprocess.Popen[bytes], free_port: int
) -> None:
    client, loop = await _connect(free_port)
    try:
        r = await client.send_command("core.info", {"type": "core.info", "client": "test"})
        root = Path(str(r["repo_root"]))
        assert (root / "pyproject.toml").exists(), f"repo_root 不是仓库根：{root}"
        assert (root / "src" / "iwan_claude").exists()
        assert Path(str(r["cwd"])).exists()
        assert str(r["config_path"]).endswith(".toml")
        assert int(r["port"]) == free_port
        assert int(r["uptime_ms"]) >= 0
        assert str(r["server_version"])
    finally:
        loop.cancel()
        await client.close()


# 功能：核心字段集合固定，且不含任何密钥/令牌类字段
# 设计：GUI 会把这行响应原样吞进渲染层；多一个 token/key 字段就是给界面开口子。
#       用集合相等而不是子集断言——新增字段必须显式改测试，逼着作者想清楚要不要暴露
async def test_core_info_exposes_no_secret_fields(
    running_daemon: subprocess.Popen[bytes], free_port: int
) -> None:
    client, loop = await _connect(free_port)
    try:
        r = await client.send_command("core.info", {"type": "core.info", "client": "gui"})
        assert set(r) == {
            "server_version",
            "uptime_ms",
            "host",
            "port",
            "cwd",
            "repo_root",
            "config_path",
            "received_at",
        }
        blob = " ".join(str(v) for v in r.values()).lower()
        for forbidden in ("api_key", "secret", "token", "password"):
            assert forbidden not in blob
    finally:
        loop.cancel()
        await client.close()


# 功能：省略 client 参数也能工作（老客户端/手动探测的默认路径）
# 设计：命令的 client 字段给了默认值就该真的可用；否则 GUI 少传一个字段就整条命令失败
async def test_core_info_accepts_missing_client(
    running_daemon: subprocess.Popen[bytes], free_port: int
) -> None:
    client, loop = await _connect(free_port)
    try:
        r = await client.send_command("core.info", {"type": "core.info"})
        assert int(r["port"]) == free_port
    finally:
        loop.cancel()
        await client.close()
