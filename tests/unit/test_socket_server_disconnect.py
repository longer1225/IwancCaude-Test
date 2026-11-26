"""客户端异常断连的日志卫生（BUG-5）

【覆盖的语义】
1. 客户端被强杀（RST）时，daemon 侧只记一行 debug，**不得**打印 Traceback
2. "读循环空闲"、"半帧未读完"、"握手阶段就断"、"命令在跑时断" 四种时机都要覆盖——
   旧实现只在读循环里处理了 LimitOverrunError，RST 会一路冒泡到 _handle_connection
   的 task，asyncio 的异常处理器再打整段回溯
3. 断连之后 daemon 仍能正常服务新连接（不能因为一次断连把 server 弄坏）

【判据为什么用"asyncio 未处理异常"+"日志无 Traceback"】
BUG-5 的现象是日志被污染而不是进程崩了，所以断言点必须落在 asyncio 的异常处理器与
日志记录上；只看"函数没抛异常"是抓不到的（异常是在 task 结束时才被上报的）。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
from collections.abc import AsyncIterator
from typing import Any

import pytest

from iwan_claude.core.transport.socket_server import SocketServer

# --- helpers -----------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _ping_handler(params: dict[str, Any]) -> dict[str, Any]:
    return {"type": "core.pong", "client": params.get("client", "")}


@pytest.fixture
async def running_server() -> AsyncIterator[int]:
    port = _free_port()
    server = SocketServer("127.0.0.1", port)
    server.register("core.ping", _ping_handler)
    await server.start()
    try:
        yield port
    finally:
        await server.stop()


@contextlib.asynccontextmanager
async def _capture_unhandled() -> AsyncIterator[list[dict[str, Any]]]:
    """收集 asyncio 的未处理异常（task 结束时冒出来的那些回溯）。

    【为什么用上下文管理器而不是 fixture】pytest-asyncio 的同步 fixture 在事件循环
    之外执行，3.12 上 asyncio.get_event_loop() 直接抛 RuntimeError；在用例体内拿
    正在跑的循环既准确又不依赖插件行为。
    """
    loop = asyncio.get_running_loop()
    captured: list[dict[str, Any]] = []

    def _handler(_loop: asyncio.AbstractEventLoop, ctx: dict[str, Any]) -> None:
        captured.append(ctx)

    old = loop.get_exception_handler()
    loop.set_exception_handler(_handler)
    try:
        yield captured
    finally:
        loop.set_exception_handler(old)


def _assert_log_clean(caplog: pytest.LogCaptureFixture) -> None:
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [], f"断连不应产生 ERROR 日志：{[r.getMessage() for r in errors]}"
    assert "Traceback" not in caplog.text


# --- 用例 --------------------------------------------------------------------


# 功能：连接空闲时被强杀（RST），daemon 侧不得打 Traceback
# 设计：transport.abort() 发 RST 而不是 FIN——FIN 走的是"读到空行正常返回"的路径，
#       抓不到 BUG-5；只有 RST 才会让 readline 抛 ConnectionResetError
async def test_rst_while_idle_does_not_log_traceback(
    running_server: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="iwan_claude.core.transport.socket_server")
    async with _capture_unhandled() as unhandled:
        _reader, writer = await asyncio.open_connection("127.0.0.1", running_server)
        await asyncio.sleep(0.05)
        writer.transport.abort()
        await asyncio.sleep(0.2)

    _assert_log_clean(caplog)
    assert unhandled == [], f"asyncio 报了未处理异常：{unhandled}"


# 功能：帧读到一半就断（半行 JSON，没有换行符），同样不得打 Traceback
# 设计：这条覆盖"已进 readline 但缓冲区非空"的时机，与空闲断连走的是不同的
#       StreamReader 分支（_wait_for_data → 抛 RST）
async def test_rst_after_partial_frame_does_not_log_traceback(
    running_server: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="iwan_claude.core.transport.socket_server")
    async with _capture_unhandled() as unhandled:
        _reader, writer = await asyncio.open_connection("127.0.0.1", running_server)
        writer.write(b'{"jsonrpc": "2.0", "id": "half", "method": "core.ping"')
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.transport.abort()
        await asyncio.sleep(0.2)

    _assert_log_clean(caplog)
    assert unhandled == []


# 功能：发完命令、不等应答就断——handler 返回时对端已消失，写回失败也不能炸
# 设计：这是"用户强杀 GUI 时正好有一次命令在跑"的真实场景，走的是 _send_quietly
#       那条路；旧实现的错误分支还会用裸 _send，写失败直接变 task 回溯
async def test_rst_after_command_does_not_log_traceback(
    running_server: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="iwan_claude.core.transport.socket_server")
    async with _capture_unhandled() as unhandled:
        _reader, writer = await asyncio.open_connection("127.0.0.1", running_server)
        req = {
            "jsonrpc": "2.0",
            "id": "abort-1",
            "method": "core.ping",
            "params": {"type": "core.ping", "client": "test"},
        }
        writer.write((json.dumps(req) + "\n").encode())
        await writer.drain()
        writer.transport.abort()
        await asyncio.sleep(0.2)

    _assert_log_clean(caplog)
    assert unhandled == []


# 功能：握手阶段被强杀（token 模式），同样静默
# 设计：_authenticate 里的 readline 是第二条"会收到 RST 的读路径"，只修 _read_loop
#       会让 token 部署下的日志继续被污染
async def test_rst_during_handshake_does_not_log_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="iwan_claude.core.transport.socket_server")
    port = _free_port()
    server = SocketServer("127.0.0.1", port, token="sekrit")
    await server.start()
    try:
        async with _capture_unhandled() as unhandled:
            _reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await asyncio.sleep(0.05)
            writer.transport.abort()
            await asyncio.sleep(0.2)
    finally:
        await server.stop()

    _assert_log_clean(caplog)
    assert unhandled == []


# 功能：一次 RST 之后 daemon 仍能正常接受新连接并应答
# 设计：只断言"没报错"会把"读循环收尾把 server 也关了"这种情况漏掉，
#       所以重新连一次并跑通一次真实请求
async def test_server_still_serves_after_client_abort(
    running_server: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="iwan_claude.core.transport.socket_server")

    _reader, writer = await asyncio.open_connection("127.0.0.1", running_server)
    writer.transport.abort()
    await asyncio.sleep(0.1)

    reader2, writer2 = await asyncio.open_connection("127.0.0.1", running_server)
    try:
        req = {
            "jsonrpc": "2.0",
            "id": "after-abort",
            "method": "core.ping",
            "params": {"type": "core.ping", "client": "test"},
        }
        writer2.write((json.dumps(req) + "\n").encode())
        await writer2.drain()
        line = await asyncio.wait_for(reader2.readline(), timeout=5.0)
        obj = json.loads(line)
        assert obj["result"]["type"] == "core.pong"
    finally:
        writer2.close()
        await writer2.wait_closed()
