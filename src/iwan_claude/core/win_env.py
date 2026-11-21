"""Windows 环境变量兜底 —— 进程环境里没有时，回头去注册表读用户级/系统级变量

【为什么需要】
`os.environ` 只是"进程启动那一刻继承到的环境块"。用户在 Windows 系统设置里新加的
`DEEPSEEK_API_KEY`，对**已经在跑**的进程不可见；而 GUI 又是 spawn daemon 的父进程，
daemon 继承的是 GUI 的环境块 —— 于是报 `DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) not set`，
用户看着"我明明配了"却不知道差在哪。

Windows 上这两个作用域另有权威存储：
    HKCU\\Environment                                  （用户级，无需管理员）
    HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment（系统级）
读取顺序与 Windows 自身解析一致：进程环境 > 用户级注册表 > 系统级注册表。
（进程环境优先：用户用 $env:X 临时覆盖时必须赢。）

【安全纪律】
- 只补调用方点名的少数变量（密钥白名单），绝不整表导入注册表；
- 只读、只写 os.environ 的内存副本，不落盘、不回显值、日志里只记变量名；
- 非 Windows 平台 no-op；设 IWAN_DISABLE_WIN_ENV_FALLBACK=1 可整体关闭（测试隔离用）。

【为什么不顺手兜底 IWAN_GITHUB_TOKEN】
测试里用"显式设空"来屏蔽 .env 中的真实令牌（见 tests/conftest.py），注册表兜底会让
空串重新变成真值、把离线用例变成线上调用——GitHub 令牌必须显式配置，不做隐式回退。
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterable

# 关闭兜底的开关：tests/conftest.py 会设，否则开发机真实 key 会渗进"预期无 key"的用例
_DISABLE_FLAG = "IWAN_DISABLE_WIN_ENV_FALLBACK"

# 用户级环境变量所在的注册表键（HKCU 下）
_USER_KEY = "Environment"

# 系统级环境变量所在的注册表键（HKLM 下）
_MACHINE_KEY = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


# 判断当前平台是否是 Windows
def _is_windows() -> bool:
    return sys.platform.startswith("win")


# 兜底是否启用：非 Windows 或被显式关闭时为 False
def _enabled() -> bool:
    return _is_windows() and not os.environ.get(_DISABLE_FLAG)


# 从注册表读一个环境变量（先用户级、再系统级），并展开值里可能存在的 %VAR%
def _read_registry(name: str) -> str:
    import winreg  # 仅 Windows 存在；放在函数内保证非 Windows 平台可正常导入本模块

    for root, sub_key in (
        (winreg.HKEY_CURRENT_USER, _USER_KEY),
        (winreg.HKEY_LOCAL_MACHINE, _MACHINE_KEY),
    ):
        try:
            with winreg.OpenKey(root, sub_key) as key:
                value, _kind = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            return os.path.expandvars(value.strip())
    return ""


# 给点名的变量做兜底注入，返回实际补齐的变量名（值一律不外泄）
def apply_env_fallback(names: Iterable[str]) -> list[str]:
    if not _enabled():
        return []
    injected: list[str] = []
    for name in names:
        # 空串也算"已显式关闭"之外的缺失：进程环境里没有非空值才回退
        if not name or os.environ.get(name):
            continue
        value = _read_registry(name)
        if value:
            os.environ[name] = value
            injected.append(name)
    return injected
