"""模型上下文窗口口径（独立模块，避免 core.config ↔ core.llm 循环导入）

【为什么单独一个模块】
窗口表同时被两处需要：
  1. `llm/provider.py`：构造 provider 时决定 context_pct 的分母
  2. `model_presets.py`：解析档位时决定每一档的窗口
而 `model_presets ← config ← llm/__init__` 已经是一条导入链，把表留在 llm 包里会让
model_presets 反过来依赖整个 llm 包（循环导入）。本模块只依赖 logging，谁都能用。

【权威顺序】显式配置（config / 环境变量） > 内置模型表 > 默认值 128K
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# 模型上下文窗口映射表
# key: 模型名称，value: 最大 token 数
# 【口径】只收录"厂商公开窗口值"，且两个厂商的模型名都必须能查到：
#   - Anthropic：claude-* 系列 200K
#   - DeepSeek：deepseek-chat / deepseek-reasoner 均为 128K
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-opus-4-7": 200_000,
    "claude-opus-4-1-20250805": 200_000,
    "deepseek-chat": 128_000,
    "deepseek-reasoner": 128_000,
}

# 表中查不到模型时的兜底窗口
# 【为什么是 128K 而不是 200K】旧实现静默返回 200_000：接的是 128K 端点时，
# 上下文占用率会被系统性低估（context_pct 最多只算到 0.64），压缩水线永远不触发。
# 宁可按更小的窗口保守计算（该压缩时提前压缩），也不要乐观低估。
DEFAULT_CONTEXT_WINDOW = 128_000

# 模型名前缀 → 厂商
_MODEL_VENDORS: tuple[tuple[str, str], ...] = (
    ("claude-", "anthropic"),
    ("deepseek-", "deepseek"),
)

# 端点（base_url）特征 → 厂商
_ENDPOINT_VENDORS: tuple[tuple[str, str], ...] = (
    ("api.anthropic.com", "anthropic"),
    ("deepseek", "deepseek"),
)


def resolve_context_window(model: str, override: int | None = None) -> int:
    """
    解析模型的有效上下文窗口 token 数

    参数：
        model: 模型名称
        override: 显式配置的覆盖值（None 或非正值 = 未配置）

    返回值：
        int: 有效上下文窗口
    """
    if override is not None and override > 0:
        return override
    window = MODEL_CONTEXT_WINDOWS.get(model)
    if window is not None:
        return window
    log.debug(
        "unknown model %r: context window falls back to %d", model, DEFAULT_CONTEXT_WINDOW
    )
    return DEFAULT_CONTEXT_WINDOW


def model_vendor(model: str) -> str | None:
    """
    按模型名前缀判断厂商

    参数：
        model: 模型名称

    返回值：
        str | None: "anthropic" / "deepseek"；无法识别时 None
    """
    lowered = model.strip().lower()
    for prefix, vendor in _MODEL_VENDORS:
        if lowered.startswith(prefix):
            return vendor
    return None


def endpoint_vendor(base_url: str) -> str | None:
    """
    按 base_url 判断厂商

    参数：
        base_url: LLM 端点地址（anthropic 协议或 openai 兼容协议均可）

    返回值：
        str | None: "anthropic" / "deepseek"；无法识别时 None
    """
    lowered = (base_url or "").strip().lower()
    for marker, vendor in _ENDPOINT_VENDORS:
        if marker in lowered:
            return vendor
    return None


def vendor_mismatch(model: str, base_url: str) -> tuple[str, str] | None:
    """
    判断"模型名与端点是否属于不同厂商"

    参数：
        model: 模型名称
        base_url: LLM 端点地址

    返回值：
        tuple[str, str] | None: 不匹配时返回 (模型厂商, 端点厂商)，否则 None

    【为什么要这个判断】内置档位表混着两家厂商的模型名。用户把 base_url 指向
    DeepSeek 却解析出 claude-* 时，请求一定 404——这是 BUG-4 现象 2。
    """
    model_v = model_vendor(model)
    endpoint_v = endpoint_vendor(base_url)
    if model_v and endpoint_v and model_v != endpoint_v:
        return model_v, endpoint_v
    return None
