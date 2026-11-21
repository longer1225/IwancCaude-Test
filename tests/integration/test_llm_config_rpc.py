"""llm.config.* / llm.set_preset 的 RPC 级集成测试

【覆盖的语义】
1. 读快照：daemon 报的是"现在真正在用"的模型与密钥来源，且把会盖住配置的
   环境变量列出来（GUI 的警告条就靠它，用户才不会把"重启后又变回去"当 bug）
2. 保存：校验 → 写 config.toml + secrets.env → 内存立即生效；回包里绝不出现 key 明文
3. 切档：不需要会话（顶部入口在任何时候都能用），并把选择落盘到 [agent] model_preset
4. 校验失败：provider/模型/key 非法时返回 INVALID_PARAMS，而不是写坏配置文件
5. 连通性测试：端点不可达时 ok=false 且带真实错误
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from iwan_claude.core.transport.socket_client import IpcError, SocketClient


# 功能：把这次测试的 daemon 配置改道到 tmp，并固定 IWAN_LLM_* 覆盖值
# 设计：仓库根的 .env 会设 IWAN_LLM_BASE_URL 等变量（真实开发机如此），不固定住
#       它们，"环境变量覆盖"的断言就只能碰运气；IWAN_CONFIG 改道保证测试不写用户的
#       ~/.iwan/config.toml（deleting/overwriting 用户模型配置是不可接受的副作用）
@pytest.fixture
def daemon_env(tmp_path: Path) -> dict[str, str]:
    return {
        "IWAN_CONFIG": str(tmp_path / "config.toml"),
        "IWAN_SECRETS_FILE": str(tmp_path / "secrets.env"),
        "IWAN_LLM_PROVIDER": "anthropic",
        "IWAN_LLM_BASE_URL": "http://127.0.0.1:9",
        "IWAN_LLM_DEFAULT_MODEL": "env-shadowed-model",
        "IWAN_LLM_CONTEXT_WINDOW": "128000",
        "IWAN_LLM_API_KEY_ENV": "DEEPSEEK_API_KEY",
        "IWAN_MODEL_PRESET": "balanced",
    }


# 功能：连上 daemon 并启动事件循环（send_command 依赖循环完成任务兑现）
# 设计：与 workspace.delete 用例同一套 helper 形式：把"连接 + 循环任务"封起来，
#       每个用例自己保证 finally 里取消循环、断开连接，避免残留任务污染下一个测试
async def _connect(port: int) -> tuple[SocketClient, asyncio.Task[None]]:
    client = SocketClient("127.0.0.1", port)
    await client.connect()
    task = asyncio.create_task(client.run_event_loop())
    return client, task


# 功能：llm.config.get 返回内存生效值、密钥来源、三档实际模型名与环境变量覆盖清单
# 设计：环境变量把 base_url/default_model 钉成已知值，断言 daemon 报的正是这些
#       （而不是 config.toml 默认值）——GUI 展示"现在真正在用"的前提
async def test_get_reports_effective_config(
    running_daemon: subprocess.Popen[bytes], free_port: int
) -> None:
    client, loop = await _connect(free_port)
    try:
        r = await client.send_command("llm.config.get", {})
        assert r["provider"] == "anthropic"
        assert r["base_url"] == "http://127.0.0.1:9"
        assert r["default_model"] == "env-shadowed-model"
        assert r["context_window"] == 128000
        assert set(r["presets"]) == {"fast", "balanced", "powerful"}
        # 没有档位覆盖时三档都跟随 [llm] default_model（内置表混着两家服务商的名字，不能用）
        assert set(r["presets"].values()) == {"env-shadowed-model"}
        assert r["preset_overrides"] == []
        assert r["active_preset"] == "balanced"
        # conftest 保证 DEEPSEEK_API_KEY 一定有值（真 key 或假 key），来源必然是环境变量
        assert r["api_key_set"] is True
        assert r["api_key_source"] == "env"
        # 尾号提示存在时形如 "…abcd"（真实 key 未知，只断言形状与长度）
        assert r["api_key_hint"] == "" or r["api_key_hint"].startswith("…")
        assert len(r["api_key_hint"]) <= 5
        assert "IWAN_LLM_BASE_URL" in r["env_overrides"]
        assert r["api_key_env"] == "DEEPSEEK_API_KEY"
    finally:
        loop.cancel()
        await client.close()


# 功能：llm.config.set 保存模型/端点/key 后，内存立即生效且落盘（config + secrets）
# 设计：一次提交覆盖全部字段，断言"回包快照/磁盘内容/密钥文件"三者一致；
#       另外断言回包 JSON 里不含 key 明文——事件与回包都会进客户端日志
async def test_set_persists_and_applies(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path: Path
) -> None:
    client, loop = await _connect(free_port)
    try:
        r = await client.send_command("llm.config.set", {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "context_window": 64000,
            "presets": {"fast": "deepseek-chat", "balanced": "deepseek-reasoner", "powerful": ""},
            "api_key": "sk-test-abcdef123456",
        })

        # 内存生效
        assert r["provider"] == "openai_compatible"
        assert r["base_url"] == "https://api.deepseek.com/v1"
        assert r["default_model"] == "deepseek-chat"
        assert r["context_window"] == 64000
        assert r["api_key_set"] is True
        assert r["api_key_source"] == "secrets"
        assert r["api_key_hint"] == "…3456"
        assert r["presets"]["fast"] == "deepseek-chat"
        assert r["presets"]["balanced"] == "deepseek-reasoner"
        # 空串 = 删掉该档覆盖，回落到默认模型（这一轮刚把默认模型改成 deepseek-chat）
        assert r["presets"]["powerful"] == "deepseek-chat"
        assert sorted(r["preset_overrides"]) == ["balanced", "fast"]
        # 环境变量会盖回旧值：必须明确提示（否则重启后就是"设置丢失"）
        assert any("IWAN_LLM_BASE_URL" in w for w in r["warnings"])

        # 落盘：config.toml 的 [llm] 与 [llm.presets] 都写进去了
        text = (tmp_path / "config.toml").read_text(encoding="utf-8")
        assert "[llm]" in text
        assert 'default_model = "deepseek-chat"' in text
        assert "[llm.presets]" in text
        assert 'fast = "deepseek-chat"' in text
        # 落盘：密钥文件里有 key（GUI 重启后 daemon 还会读它）
        assert "sk-test-abcdef123456" in (tmp_path / "secrets.env").read_text(encoding="utf-8")
        # 回包绝不带 key 明文
        assert "sk-test-abcdef123456" not in json.dumps(r, ensure_ascii=False)
    finally:
        loop.cancel()
        await client.close()


# 功能：llm.set_preset 无需会话即可全局切档，模型名随覆盖表解析，并把选择落盘
# 设计：先保存覆盖表再切档，断言回包的 model 是覆盖后的名字（而不是内置 claude-*）；
#       再断言 [agent] model_preset 落盘——否则重启 daemon 会悄悄回到 balanced
async def test_set_preset_global_and_persisted(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path: Path
) -> None:
    client, loop = await _connect(free_port)
    try:
        await client.send_command("llm.config.set", {
            "presets": {"fast": "deepseek-chat", "balanced": "deepseek-reasoner"},
        })
        r = await client.send_command("llm.set_preset", {"preset": "fast"})
        assert r == {"preset": "fast", "model": "deepseek-chat"}

        snapshot = await client.send_command("llm.config.get", {})
        assert snapshot["active_preset"] == "fast"

        text = (tmp_path / "config.toml").read_text(encoding="utf-8")
        assert "[agent]" in text
        assert 'model_preset = "fast"' in text
    finally:
        loop.cancel()
        await client.close()


# 功能：非法 provider / 空模型 / 短 key 都返回 INVALID_PARAMS，且不改动磁盘配置
# 设计：错误路径最容易写坏文件（校验后置的写法会先落盘再报错）；这里断言异常
#       带 JSON-RPC 的 -32602，并且 config.toml 依然不存在（本次提交没有落下任何东西）
async def test_invalid_values_rejected_without_side_effects(
    running_daemon: subprocess.Popen[bytes], free_port: int, tmp_path: Path
) -> None:
    client, loop = await _connect(free_port)
    try:
        for params in (
            {"provider": "bogus"},
            {"default_model": "   "},
            {"base_url": "ftp://x"},
            {"context_window": 10},
            {"presets": {"turbo": "x"}},
            {"api_key": "short"},
        ):
            with pytest.raises(IpcError) as exc:
                await client.send_command("llm.config.set", params)
            assert exc.value.code == -32602, params
        assert not (tmp_path / "config.toml").exists()
        assert not (tmp_path / "secrets.env").exists()
    finally:
        loop.cancel()
        await client.close()


# 功能：llm.config.test 在端点不可达时返回 ok=false 且带可读错误
# 设计：这就是"保存成功≠能用"的兜底：用死端口（127.0.0.1:9）让连接立即失败，
#       断言错误文案非空、模型名是档位解析后的值——GUI 据此显示真实原因
async def test_config_test_reports_failure(
    running_daemon: subprocess.Popen[bytes], free_port: int
) -> None:
    client, loop = await _connect(free_port)
    try:
        await client.send_command("llm.config.set", {
            "presets": {"balanced": "deepseek-reasoner"},
            "api_key": "sk-test-abcdef123456",
        })
        r = await client.send_command("llm.config.test", {})
        assert r["ok"] is False
        assert r["model"] == "deepseek-reasoner"
        assert r["error"]
        assert "sk-test-abcdef123456" not in json.dumps(r, ensure_ascii=False)
    finally:
        loop.cancel()
        await client.close()
