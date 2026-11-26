"""上下文窗口口径回归（BUG-1）

【覆盖的语义】
1. 未显式配置 `[llm] context_window` / `IWAN_LLM_CONTEXT_WINDOW` 时，provider 必须
   **按模型查表**：claude-* 200K、deepseek-* 128K——而不是一律按 128K 算
2. 内置表里必须收录 DeepSeek 两个模型（旧表只有 claude，deepseek 被算成 200K）
3. 未知模型不再静默按 200K 算，而是回落到 128K 默认值并记 debug
4. 显式配置值优先级最高（config / 环境变量都能生效）
5. 两个 provider（anthropic / openai_compatible）口径一致

【为什么这些用例能抓住 BUG-1】
旧实现的 `LlmConfig.context_window` 默认值是 128_000（永远非 None），
`create_provider_from_config()` 无条件把它当 `context_window_override` 传下去，
于是 `_effective_context_window()` 里"查表"那条分支从未被执行过。
下面第 2 组用例直接断言"工厂出来的 provider 报的是表里的值"，修复前必失败。
"""
from __future__ import annotations

import logging
from typing import Any

import pytest

from iwan_claude.core.config import LlmConfig
from iwan_claude.core.context_window import (
    DEFAULT_CONTEXT_WINDOW,
    MODEL_CONTEXT_WINDOWS,
    resolve_context_window,
)
from iwan_claude.core.llm import create_provider_from_config
from iwan_claude.core.llm.openai_compat import OpenAICompatibleProvider
from iwan_claude.core.llm.provider import AnthropicProvider, _context_window

# --- helpers -----------------------------------------------------------------


class _FakeAnthropicClient:
    """构造 AnthropicProvider 时跳过真实 SDK 与 API Key 校验"""


def _fake_http_client() -> Any:
    """openai_compatible provider 只需要一个可注入的 http 客户端占位"""
    return object()


# --- 1. 查表函数本身 ---------------------------------------------------------


# 功能：内置表必须同时收录两家厂商的模型（旧表没有 deepseek 任何一项）
# 设计：直接断言表内容而不是只断言函数返回值——表缺项是 BUG-1 的现象 2，
#       用返回值断言在"兜底值恰好等于期望值"时会假绿
def test_model_table_contains_both_vendors() -> None:
    assert MODEL_CONTEXT_WINDOWS["deepseek-chat"] == 128_000
    assert MODEL_CONTEXT_WINDOWS["deepseek-reasoner"] == 128_000
    assert MODEL_CONTEXT_WINDOWS["claude-sonnet-4-6"] == 200_000


# 功能：已知模型按表返回（claude 200K / deepseek 128K）
# 设计：参数化两个厂商，避免只测一家就宣称"查表分支已覆盖"
@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-sonnet-4-6", 200_000),
        ("claude-haiku-4-5-20251001", 200_000),
        ("deepseek-chat", 128_000),
        ("deepseek-reasoner", 128_000),
    ],
)
def test_known_models_use_table(model: str, expected: int) -> None:
    assert resolve_context_window(model) == expected
    # 历史兼容入口必须与新入口同口径，否则老调用方仍会拿到旧值
    assert _context_window(model) == expected


# 功能：未知模型回落到默认值（128K），且留下 debug 记录
# 设计：断言日志是本条的核心——"静默"正是 BUG-1 第三个现象的恶劣之处，
#       只断言数值的话，将来有人把默认值改回 200K 也不会有测试报警
def test_unknown_model_falls_back_to_default_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="iwan_claude.core.context_window"):
        window = resolve_context_window("unknown-model-xyz")
    assert window == DEFAULT_CONTEXT_WINDOW == 128_000
    assert any("unknown-model-xyz" in rec.getMessage() for rec in caplog.records)


# 功能：显式覆盖值优先级最高，且非法值（None / 0 / 负数）视为未配置
# 设计：0 与负数走查表分支是防御性代码，单独覆盖——它们曾经是"配置错误却静默生效"的来源
def test_override_wins_and_invalid_override_falls_through() -> None:
    assert resolve_context_window("claude-sonnet-4-6", 64_000) == 64_000
    assert resolve_context_window("claude-sonnet-4-6", None) == 200_000
    assert resolve_context_window("claude-sonnet-4-6", 0) == 200_000
    assert resolve_context_window("deepseek-chat", -1) == 128_000


# --- 2. 工厂 + provider 端到端（BUG-1 的判据） -------------------------------


# 功能：没配 context_window 时，工厂产出的 anthropic provider 按模型查表
# 设计：这条是 BUG-1 的正面回归——修复前 LlmConfig 默认 128_000 恒被当作覆盖值，
#       claude-sonnet-4-6 会报 128_000（表里是 200_000），用例必红
def test_factory_uses_table_when_context_window_unset() -> None:
    cfg = LlmConfig(default_model="claude-sonnet-4-6")
    provider = create_provider_from_config(cfg, anthropic_client=_FakeAnthropicClient())
    assert isinstance(provider, AnthropicProvider)
    assert provider._effective_context_window() == 200_000

    cfg_ds = LlmConfig(default_model="deepseek-chat")
    provider_ds = create_provider_from_config(cfg_ds, anthropic_client=_FakeAnthropicClient())
    assert provider_ds._effective_context_window() == 128_000


# 功能：显式配置 context_window 时，工厂产出的 provider 用配置值
# 设计：与上一条互为反向约束——只修"查表"而把"显式配置"弄丢，是更严重的回归
def test_factory_respects_explicit_context_window() -> None:
    cfg = LlmConfig(default_model="claude-sonnet-4-6", context_window=64_000)
    provider = create_provider_from_config(cfg, anthropic_client=_FakeAnthropicClient())
    assert provider._effective_context_window() == 64_000


# 功能：openai_compatible provider 与 anthropic provider 口径一致
# 设计：该 Provider 的构造参数是 int（不是 None），所以必须由工厂先解析再传；
#       两个 provider 报不同窗口会让 GUI 的占用率在同一模型下前后跳变
def test_factory_openai_compatible_uses_same_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")
    cfg = LlmConfig(
        provider="openai_compatible",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="claude-sonnet-4-6",
    )
    provider = create_provider_from_config(cfg, http_client=_fake_http_client())
    assert isinstance(provider, OpenAICompatibleProvider)
    # 未配置时按模型表解析（200K），不是构造参数的 128_000 默认值
    assert provider._context_window == 200_000


# 功能：LlmConfig 的默认值语义是"未配置"（None），而不是某个具体窗口
# 设计：这条锁住根因本身——只要有人把默认值改回 128_000，查表分支立刻再也不会执行
def test_llm_configDEFAULT_CONTEXT_WINDOW_is_unset() -> None:
    assert LlmConfig().context_window is None
