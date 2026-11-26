"""模型档位：窗口随模型走 + 端点错配告警（BUG-4）

【覆盖的语义】
1. 内置三档的 `context_window` 必须与模型窗口表一致（旧值 64K/128K/200K 是手写的，
   与真实窗口打架：`fast` 标 64K 而 deepseek-chat 实际 128K）
2. 档位被 `[llm.presets]` 覆盖成另一个模型时，窗口跟着**解析后的模型**走
   （旧实现沿用内置档位窗口：powerful → deepseek-chat 仍按 200K 算，占用率少报一半）
3. `ModelPreset.context_window` 真正参与 provider 计算（不是死字段）：未显式配置
   `[llm] context_window` 时，用它作为 context_pct 的分母
4. 只配 `[llm] default_model` 时三档确实等价 —— 这条要留下显式调试记录，
   并靠端点错配告警兜住"claude 模型名发给 DeepSeek 端点"的 404（现象 2）

【为什么不把"三档等价"直接判成缺陷】
用户只有一个模型可用时，三档等价是合理默认；真正有害的是"解析结果与端点厂商
不匹配却静默发出请求"。所以修复方向是：窗口回归模型表 + 错配告警 + 文档同步，
而不是强行给三档编造三个不同模型。
"""
from __future__ import annotations

import logging

import pytest

from iwan_claude.core.config import LlmConfig
from iwan_claude.core.context_window import MODEL_CONTEXT_WINDOWS
from iwan_claude.core.llm import create_provider_from_config
from iwan_claude.core.llm.provider import AnthropicProvider
from iwan_claude.core.model_presets import MODEL_PRESETS, resolve_preset


class _FakeClient:
    """跳过真实 SDK 与 API Key 校验"""


# --- 1. 内置档位的窗口与模型表一致 -------------------------------------------


# 功能：三档内置窗口等于其模型在窗口表里的值
# 设计：旧值写死在 model_presets.py 里（64K/128K/200K），一改模型表就脱节；
#       断言"等于表值"而不是断言具体数字，将来扩表也不会误红
@pytest.mark.parametrize("tier", ["fast", "balanced", "powerful"])
def test_builtin_preset_window_matches_model_table(tier: str) -> None:
    preset = MODEL_PRESETS[tier]
    assert preset.context_window == MODEL_CONTEXT_WINDOWS[preset.model]


# 功能：档位被覆盖成别的模型时，窗口跟着新模型走
# 设计：这是 BUG-4 现象 3 的核心断言——只改模型名不改窗口，
#       context_pct 会按错误的窗口算，压缩永远不触发
def test_override_window_follows_resolved_model() -> None:
    preset = resolve_preset("powerful", {"powerful": "deepseek-chat"}, None)
    assert preset.model == "deepseek-chat"
    assert preset.context_window == 128_000  # 不是 powerful 内置的 200K


# 功能：未知模型解析出的档位窗口回落默认值（128K），不是内置档位的窗口
# 设计：自定义端点常给私有模型名；沿用内置档位窗口会掩盖"窗口未知"这件事
def test_unknown_model_in_preset_uses_default_window() -> None:
    preset = resolve_preset("powerful", {"powerful": "my-private-model"}, None)
    assert preset.context_window == 128_000


# --- 2. 档位窗口真正参与 provider 计算（死字段 → 活字段） --------------------


# 功能：未显式配置窗口时，工厂使用档位自带的窗口
# 设计：这条把 `ModelPreset.context_window` 从"装饰字段"变成"真参数"——
#       旧实现 provider 只认 [llm] context_window，档位窗口从未被读取
def test_factory_uses_preset_window_when_config_unset() -> None:
    cfg = LlmConfig(default_model="my-private-model")
    provider = create_provider_from_config(
        cfg,
        model_override="my-private-model",
        preset_context_window=64_000,
        anthropic_client=_FakeClient(),
    )
    assert isinstance(provider, AnthropicProvider)
    assert provider._effective_context_window() == 64_000


# 功能：显式配置的 [llm] context_window 优先级高于档位窗口
# 设计：用户显式配了数就必须听用户的；档位窗口只是"没说的时候"的默认
def test_explicit_config_window_beats_preset_window() -> None:
    cfg = LlmConfig(default_model="my-private-model", context_window=32_000)
    provider = create_provider_from_config(
        cfg,
        model_override="my-private-model",
        preset_context_window=64_000,
        anthropic_client=_FakeClient(),
    )
    assert provider._effective_context_window() == 32_000


# --- 3. 只配 default_model 时的行为 ------------------------------------------


# 功能：只配 default_model 时三档解析为同一模型，并留下 debug 说明
# 设计：现象 1 的"根因解释"落成日志——用户抱怨"切档没效果"时能直接查到原因；
#       断言 debug 文案里的关键信息（三档 + default_model）而不是整句，避免文案脆弱
def test_only_default_model_logs_equivalence_hint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = LlmConfig(default_model="deepseek-chat")
    with caplog.at_level(logging.DEBUG, logger="iwan_claude.core.llm"):
        create_provider_from_config(cfg, anthropic_client=_FakeClient())

    models = {resolve_preset(t, None, cfg.default_model).model for t in ("fast", "balanced", "powerful")}
    assert models == {"deepseek-chat"}
    assert any("default_model" in rec.getMessage() and "三档" in rec.getMessage() for rec in caplog.records)


# --- 4. 端点与模型厂商错配的明确告警 ----------------------------------------


# 功能：claude 模型名 + DeepSeek 端点 → 明确告警（含 404 与修法提示）
# 设计：BUG-4 现象 2 的可观测面。只断言"有 warning"不够，必须断言它说清了
#       哪里不一致、怎么改，否则用户仍然只能靠猜
def test_vendor_mismatch_warns_clearly(caplog: pytest.LogCaptureFixture) -> None:
    cfg = LlmConfig(
        base_url="https://api.deepseek.com/anthropic",
        default_model="claude-opus-4-1-20250805",
    )
    with caplog.at_level(logging.WARNING, logger="iwan_claude.core.llm"):
        create_provider_from_config(cfg, anthropic_client=_FakeClient())

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "厂商错配必须给告警"
    text = warnings[0]
    assert "404" in text
    assert "deepseek" in text and "anthropic" in text
    assert "default_model" in text and "presets" in text


# 功能：端点与模型同厂商时不告警（避免狼来了）
# 设计：误报会让告警失去意义；DeepSeek 端点 + deepseek-chat 是最常见正确配置
def test_no_warning_when_vendor_matches(caplog: pytest.LogCaptureFixture) -> None:
    cfg = LlmConfig(
        base_url="https://api.deepseek.com/anthropic",
        default_model="deepseek-chat",
    )
    with caplog.at_level(logging.WARNING, logger="iwan_claude.core.llm"):
        create_provider_from_config(cfg, anthropic_client=_FakeClient())

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# 功能：无法识别的厂商/端点（自定义网关）不告警
# 设计：私有聚合网关很常见，识别不出厂商就下结论会制造噪音
def test_no_warning_when_vendor_unknown(caplog: pytest.LogCaptureFixture) -> None:
    cfg = LlmConfig(base_url="http://127.0.0.1:8080/v1", default_model="my-private-model")
    with caplog.at_level(logging.WARNING, logger="iwan_claude.core.llm"):
        create_provider_from_config(cfg, anthropic_client=_FakeClient())

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
