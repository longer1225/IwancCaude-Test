"""模型档位解析（model_presets.resolve_preset）的单元测试

【被测对象】resolve_preset：把 config 的 [llm.presets] 覆盖叠到内置三档上
【为什么值得单独测】它是"换模型"真正生效的最后一步：如果覆盖没接进这里，
GUI 里保存的模型名只是写进了 config.toml，runner 仍会拿内置的 claude-* 去打
DeepSeek 端点——界面显示正确、运行必失败，最难排查的一类不一致。
"""
from __future__ import annotations

from iwan_claude.core.model_presets import MODEL_PRESETS, resolve_preset


# 功能：没有覆盖、也没有默认模型时返回内置档位（模型名与上下文窗口都不变）
# 设计：兼容"老用户什么都没配"的主路径；用 is 断言对象同一性，确认没走多余拷贝
def test_no_override_returns_builtin() -> None:
    preset = resolve_preset("balanced", None, None)

    assert preset is MODEL_PRESETS["balanced"]
    assert resolve_preset("balanced", {}, None) is MODEL_PRESETS["balanced"]
    assert resolve_preset("balanced") is MODEL_PRESETS["balanced"]


# 功能：没有档位覆盖时，默认模型（[llm] default_model）优先于内置表
# 设计：这是"我明明配了 deepseek-chat，跑起来却是 claude-sonnet-4-6"的修复点：
#       内置表混着两家服务商的模型名，任何单一端点都不可能三个都认
def test_default_model_fills_missing_tiers() -> None:
    for tier in ("fast", "balanced", "powerful"):
        assert resolve_preset(tier, None, "deepseek-chat").model == "deepseek-chat"


# 功能：档位覆盖 > 默认模型（显式配置必须赢）
# 设计：三层解析顺序的核心断言；顺序错了会出现"设置了某档却不生效"
def test_override_beats_default_model() -> None:
    preset = resolve_preset("fast", {"fast": "deepseek-reasoner"}, "deepseek-chat")

    assert preset.model == "deepseek-reasoner"
    assert preset.context_window == MODEL_PRESETS["fast"].context_window
    assert preset.description == MODEL_PRESETS["fast"].description


# 功能：覆盖表里没有该档（或值为空白）时回退内置模型名
# 设计：GUI 提交空串代表"删掉该档覆盖"，解析层必须把空白当"没配"，
#       否则会拿空模型名去发请求
def test_missing_or_blank_override_falls_back() -> None:
    assert resolve_preset("powerful", {"fast": "x"}).model == MODEL_PRESETS["powerful"].model
    assert resolve_preset("fast", {"fast": "   "}).model == MODEL_PRESETS["fast"].model


# 功能：非法档位名与 get_model_preset 一致地回退到 balanced
# 设计：档位来自客户端字符串，回退规则必须与既有 API 相同，否则同一非法输入在
#       "设置"和"解析"两处得到不同模型，事件里展示的名字会与实际调用不一致
def test_unknown_preset_falls_back_to_balanced() -> None:
    assert resolve_preset("turbo", {}).model == MODEL_PRESETS["balanced"].model
