"""
本机密钥文件 - `~/.iwan/secrets.env`：GUI 写、daemon 读的"用户显式密钥"层

【为什么单独一个文件，而不是塞进 config.toml 或仓库根的 .env】
1. config.toml 是后端行为契约，可能被提交/分享进仓库；密钥不该混在契约里
2. 仓库根的 .env 属"项目级配置"，agent 不许改它（AGENTS.md），GUI 也不该动
3. 单独一份用户级文件，权限只需管这一份（尽量 0600），删掉即回到纯环境变量模式

【优先级语义（与 config.py 的四层不同，这里只有两层）】
- 本文件里【有】的变量：以本文件为准（注入 os.environ 时 override）
  理由：用户在 GUI 里刚填的 key 是"最新一次显式动作"，不该被半年前写的 .env 盖掉；
  GUI 会明确显示"key 来源"与"已覆盖环境变量"，不存在悄悄生效
- 本文件里【没有】的变量：完全不动 os.environ（环境变量、.env 该赢就赢）

【安全纪律】
- 本模块只把值送进 os.environ，绝不返回给客户端：RPC 层只对外给"是否设置 + 尾号"
- 不写日志、不进 trace；bash 工具的环境洗刷规则（*_API_KEY）本来就会摘掉它们
- 文件名带 .env 后缀：与 dotenv 生态同形，用户一眼知道"这里存的是密钥"
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values

# 环境变量：改道本机密钥文件路径（测试/CI 用，避免读开发机上的真实 key）
_ENV_PATH = "IWAN_SECRETS_FILE"
# 默认位置：与 config.toml / gui.json / trust.toml 同级
_DEFAULT_PATH = "~/.iwan/secrets.env"

# 本次进程里"由本文件注入/覆盖"的变量名 → 注入前的旧值（删除密钥时要还原）
_applied: dict[str, str | None] = {}

# 密钥名合法性：环境变量名形态（大写+数字+下划线），挡掉注入奇怪名字的路径
_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


# 本机密钥文件路径（IWAN_SECRETS_FILE > ~/.iwan/secrets.env）
def secrets_path() -> Path:
    return Path(os.environ.get(_ENV_PATH, _DEFAULT_PATH)).expanduser()


# 读取本机密钥文件（缺文件/坏行都返回空表，不让诊断本身变成故障）
def read_secrets() -> dict[str, str]:
    path = secrets_path()
    if not path.exists():
        return {}
    try:
        raw = dotenv_values(path)
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        name = str(key).strip()
        if _NAME_RE.match(name):
            out[name] = value
    return out


# 校验密钥名（非法名字一律拒绝：它要成为环境变量，也决定 scrub 规则能否命中）
def validate_secret_name(name: str) -> str:
    value = (name or "").strip()
    if not _NAME_RE.match(value):
        raise ValueError(f"非法密钥变量名：{name!r}（须形如 DEEPSEEK_API_KEY）")
    return value


# 校验密钥值（ASCII 可见、非空；HTTP 头只吃 ASCII，中文/弯引号必须当场拦下）
def validate_secret_value(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("密钥不能为空")
    if len(raw) < 8:
        raise ValueError("密钥太短（至少 8 个字符），请检查是否粘贴完整")
    bad = next((c for c in raw if ord(c) > 126 or ord(c) < 33), None)
    if bad is not None:
        raise ValueError(
            f"密钥含非法字符 {bad!r}（U+{ord(bad):04X}）：只能有 ASCII 可见字符（不含空格），"
            "常见原因是把中文提示词或弯引号一起粘了进来"
        )
    return raw


# dotenv 值加双引号并转义反斜杠/引号（裸值里的 # 或空格会被解析成注释/截断）
def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# 原子写整份密钥文件（同目录临时文件 + os.replace，权限尽量收到 0600）
def _write_all(entries: dict[str, str]) -> None:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# iwanclaude 本机密钥（GUI「模型与 API」写入；daemon 启动时读取）",
        "# 权限：仅当前用户可读写；删掉本文件即回到纯环境变量模式",
        "",
    ]
    # 值一律加双引号转义：密钥里出现 # 或空格时，裸写的值会被 dotenv 当成注释截断
    lines += [f"{name}={_quote(value)}" for name, value in sorted(entries.items())]
    text = "\n".join(lines) + "\n"
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows 上 chmod 语义有限；权限收紧尽力而为，失败不影响功能


# 写入/更新一个密钥（同时记住注入前的旧值，供删除时还原）
def set_secret(name: str, value: str) -> None:
    key = validate_secret_name(name)
    secret = validate_secret_value(value)
    entries = read_secrets()
    entries[key] = secret
    _write_all(entries)
    _applied.setdefault(key, os.environ.get(key))
    os.environ[key] = secret


# 删除一个密钥（并从 os.environ 还原注入前的值——不是无脑 pop 掉用户环境变量）
def delete_secret(name: str) -> bool:
    key = validate_secret_name(name)
    entries = read_secrets()
    if key not in entries:
        return False
    del entries[key]
    _write_all(entries)
    if key in _applied:
        previous = _applied.pop(key)
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    return True


# 把本机密钥注入 os.environ（本文件里有的变量以本文件为准；缺口文件时是 no-op）
def apply_secrets_to_env() -> list[str]:
    entries = read_secrets()
    for key, value in entries.items():
        _applied.setdefault(key, os.environ.get(key))
        os.environ[key] = value
    return sorted(entries)


# 值尾号（给 GUI 显示"已配置 · …abcd"用；短值不显示，避免反而泄露）
def key_hint(value: str) -> str:
    if not value:
        return ""
    return f"…{value[-4:]}" if len(value) >= 12 else ""
