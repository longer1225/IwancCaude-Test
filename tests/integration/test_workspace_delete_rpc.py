"""workspace.delete 的 RPC 级集成测试

覆盖"一键删除工作区"这一整套语义：按 cwd 归一化匹配、只关该目录的会话、
不动别的工作区、可重复调用（幂等）、以及只关会话不删磁盘文件。
用真实 daemon 子进程（conftest 的 running_daemon），不依赖 LLM。
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from iwan_claude.core.transport.socket_client import SocketClient


# 功能：建一个已连上 daemon 并跑着事件循环的客户端（send_command 依赖它解析响应）
# 设计：SocketClient 的响应 Future 由 run_event_loop 完成，不启动循环就会永久挂起；
#       把"连接 + 循环任务"封在一个 helper 里，用例只关心 RPC 结果
async def _connect(port: int) -> tuple[SocketClient, asyncio.Task[None]]:
    client = SocketClient("127.0.0.1", port)
    await client.connect()
    task = asyncio.create_task(client.run_event_loop())
    return client, task


# 功能：按 cwd 归一化删除工作区——只关闭该目录下的会话，其它工作区原样保留
# 设计：A 目录 2 个会话 + B 目录 1 个会话，删除 A 之后断言 session.list 里只剩 B；
#       同时断言"再次删除 A"返回空 closed（幂等），避免 GUI 重复点击时误报失败
async def test_delete_workspace_closes_only_that_cwd(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path
) -> None:
    proj_a = tmp_path / "proj_a"
    proj_b = tmp_path / "proj_b"
    proj_a.mkdir()
    proj_b.mkdir()

    client, loop = await _connect(free_port)
    try:
        a_ids: list[str] = []
        for i in range(2):
            r = await client.send_command(
                "session.create", {"mode": "chat", "title": f"a{i}", "cwd": str(proj_a)})
            a_ids.append(r["session_id"])
        rb = await client.send_command(
            "session.create", {"mode": "chat", "title": "b0", "cwd": str(proj_b)})
        b_id = rb["session_id"]

        # cwd 用"正斜杠 + 尾部斜杠"的写法：验证服务端确实做了归一化，而不是字符串相等
        weird = str(proj_a).replace("\\", "/") + "/"
        r = await client.send_command("workspace.delete", {"cwd": weird})
        assert sorted(r["closed"]) == sorted(a_ids)
        assert r["skipped"] == []

        listed = await client.send_command("session.list", {})
        alive = {s["id"]: s["status"] for s in listed["sessions"]}
        for sid in a_ids:
            assert alive[sid] == "closed"
        assert alive[b_id] != "closed"

        # 幂等：再点一次不该把已关闭的再算进 closed
        r2 = await client.send_command("workspace.delete", {"cwd": str(proj_a)})
        assert r2["closed"] == []
        assert r2["skipped"] == []
    finally:
        loop.cancel()
        await client.close()


# 功能：删除工作区只关会话，绝不删磁盘上的文件
# 设计：先在项目目录里落一个文件，删除工作区后断言文件仍在——这是本命令最容易被
#       "顺手 rm -rf"写坏的地方，用一个真实磁盘断言把它钉住
async def test_delete_workspace_keeps_files_on_disk(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path
) -> None:
    proj = tmp_path / "proj_files"
    proj.mkdir()
    keep = proj / "keep.txt"
    keep.write_text("do not delete", encoding="utf-8")

    client, loop = await _connect(free_port)
    try:
        created = await client.send_command(
            "session.create", {"mode": "chat", "title": "t", "cwd": str(proj)})
        sid = created["session_id"]
        r = await client.send_command("workspace.delete", {"cwd": str(proj)})
        assert r["closed"] == [sid]
        assert keep.read_text(encoding="utf-8") == "do not delete"
        assert proj.is_dir()
    finally:
        loop.cancel()
        await client.close()


# 功能：删除不存在/空的工作区返回空列表而不是报错
# 设计：GUI 的菜单在"从列表移除"和"删除工作区"之间复用同一个 RPC，目录可能已经
#       被用户在文件管理器里删掉；这里断言服务端不把"没会话"当成错误
async def test_delete_empty_workspace_is_noop(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path
) -> None:
    missing = tmp_path / "nobody-here"
    client, loop = await _connect(free_port)
    try:
        r: dict[str, Any] = await client.send_command("workspace.delete", {"cwd": str(missing)})
        assert r["closed"] == []
        assert r["skipped"] == []
    finally:
        loop.cancel()
        await client.close()
