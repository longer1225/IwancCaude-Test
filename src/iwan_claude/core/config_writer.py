"""
config.toml 的"只改我管的键"写法 - GUI 保存模型/密钥设置时用

【设计原则（和"整份重写"划清界限）】
1. 绝不重排或删除用户手写的键与注释：只替换目标段里的目标键，其它字节原样保留
   —— 用户的 config.toml 里可能有 MCP、hooks、权限规则，重写=毁配置
2. 写完立刻用 tomllib 复读一遍：解析失败就回滚原文并抛错
   —— config.toml 写坏意味着 daemon 下次起不来，这个代价必须当场付掉
3. 原子替换（同目录临时文件 + os.replace）：断电/崩在写一半也不会留下半个文件
4. 行尾跟随原文（CRLF/LF 不混用）：Windows 上 git/编辑器按行尾判 diff

【调用方】
- app.py 的 llm.config.set（[llm] 与 [llm.presets]）
- app.py 的 llm.set_preset（[agent] model_preset）
"""
from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ConfigWriteError(Exception):
    """config.toml 写入失败（校验不通过已回滚，原始内容仍完整）"""


# 段头匹配：`[llm]` / `[[mcp.servers]]`（数组表永不与我们写的段名相等）
def _header_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("["):
        return None
    # 段头里不会有字符串，行尾注释直接从 # 截掉
    head = stripped.split("#", 1)[0].strip()
    return head or None


# 键行匹配：`provider = "anthropic"`（我们只写裸键名，带引号的键不接管）
def _key_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = re.match(r"^([A-Za-z0-9_-]+)\s*=", stripped)
    return match.group(1) if match else None


# TOML 字面量：字符串走 JSON 转义（反斜杠/引号/换行都能被 tomllib 原样读回）
def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


# 插入行使用的行尾：沿用原文（空文件按 LF）
def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


# 在给定段内替换/追加/删除键，返回新的全文（不碰其它段的任何字节）
def upsert_section(text: str, section: str, values: Mapping[str, Any]) -> str:
    nlb = _newline(text)
    lines = text.splitlines(keepends=True)
    target = f"[{section}]"

    start = -1
    for idx, line in enumerate(lines):
        if _header_name(line) == target:
            start = idx
            break

    # 段不存在：整段追加到文件尾（前面补空行，保持可读）
    if start < 0:
        body = "".join(f"{key} = {toml_value(val)}{nlb}" for key, val in values.items() if val != "")
        if not body:
            return text
        tail = text
        if tail and not tail.endswith(("\n", "\r")):
            tail += nlb
        if tail and not tail.endswith(nlb + nlb):
            tail += nlb
        return f"{tail}{target}{nlb}{body}"

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if _header_name(lines[idx]) is not None:
            end = idx
            break

    seen: set[str] = set()
    body_lines = lines[start + 1:end]
    new_body: list[str] = []
    for line in body_lines:
        key = _key_name(line)
        if key is not None and key in values:
            seen.add(key)
            value = values[key]
            if value == "":
                continue  # 空串 = 删除该键（例如清掉某个档位的模型覆盖）
            new_body.append(f"{key} = {toml_value(value)}{nlb}")
        else:
            new_body.append(line)

    # 段里没有的键：追加在本段末尾（下个段头之前），不破坏段外内容
    for key, value in values.items():
        if key in seen or value == "":
            continue
        new_body.append(f"{key} = {toml_value(value)}{nlb}")

    # 原段是"空段"（段头紧接下一个段头）：补一个空行让追加的键不贴死段头
    if not body_lines and new_body:
        new_body.insert(0, nlb)

    return "".join(lines[:start + 1]) + "".join(new_body) + "".join(lines[end:])


# 写入若干段：先合并出一份新全文并做 tomllib 校验，通过才落盘（失败回滚原文）
def write_config_sections(path: Path, sections: Mapping[str, Mapping[str, Any]]) -> None:
    try:
        original = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise ConfigWriteError(f"读取 config.toml 失败：{exc}") from exc

    text = original
    for section, values in sections.items():
        text = upsert_section(text, section, values)

    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigWriteError(f"写入后的 config.toml 无法解析（已回滚，原文件未改）：{exc}") from exc

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8", newline="")
        os.replace(tmp, path)
    except OSError as exc:
        raise ConfigWriteError(f"写入 config.toml 失败（原文件未改）：{exc}") from exc
