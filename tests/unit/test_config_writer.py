"""config.toml 增量写入器（config_writer）的单元测试

【被测对象】upsert_section / write_config_sections
【为什么值得单独测】它要往用户手写的配置文件里插键：一旦重排或吃掉注释，
用户的 MCP/hooks/权限规则就没了；一旦写出非法 TOML，daemon 下次直接起不来。
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from iwan_claude.core.config_writer import (
    ConfigWriteError,
    toml_value,
    upsert_section,
    write_config_sections,
)

# 用户手写的配置文件：注释、空行、别的段全都要活着
_ORIGINAL = """\
# 我的 iwan 配置
[core]
port = 7437

# MCP 服务器
[[mcp.servers]]
name = "fs"
transport = "stdio"
command = "npx"

[agent]
max_steps = 20
"""


# 功能：写 [llm] 段时不碰已有的注释、其它段和空行
# 设计：先断言"新键出现"再断言"原文的每一行都还在"——后者是这次改动的真风险：
#       整份重写会把用户的 MCP/hooks 配置抹掉，而它看起来"保存成功"
def test_upsert_preserves_other_content() -> None:
    out = upsert_section(_ORIGINAL, "llm", {"provider": "anthropic", "base_url": "https://x"})

    assert '[llm]' in out
    assert 'provider = "anthropic"' in out
    assert 'base_url = "https://x"' in out
    for line in _ORIGINAL.splitlines():
        assert line in out
    # 追加的段落在文件末尾，不会插进 [[mcp.servers]] 数组表中间
    assert out.index("[[mcp.servers]]") < out.index("[llm]")


# 功能：已有键被原地替换（不是追加第二个同名键——那会让 TOML 直接非法）
# 设计：重复键是 TOML 硬错误，但只有真去解析才看得出；这里显式断言同键只出现一次
def test_upsert_replaces_existing_key_once() -> None:
    out = upsert_section(_ORIGINAL, "agent", {"max_steps": 40})

    assert out.count("max_steps") == 1
    assert "max_steps = 40" in out


# 功能：值为空串 = 删除该键（清掉某档模型覆盖时用）
# 设计：删除必须只发生在目标段内；用 [llm.presets] 里 fast 的删除钉住"段内定位"
def test_upsert_deletes_key_on_empty_value() -> None:
    text = "[llm.presets]\nfast = \"a\"\nbalanced = \"b\"\n"
    out = upsert_section(text, "llm.presets", {"fast": ""})

    assert "fast" not in out
    assert 'balanced = "b"' in out


# 功能：段存在但为空（段头紧接下一个段头）时，新键写在该段里而不是下一个段里
# 设计：这是最容易写错的位置——插错段落会让 provider 落进 [agent]，而且
#       tomllib 依然解析成功，只有读回的值能暴露它
def test_upsert_into_empty_section() -> None:
    text = "[llm]\n[agent]\nmax_steps = 20\n"
    out = upsert_section(text, "llm", {"provider": "anthropic"})

    parsed = tomllib.loads(out)
    assert parsed["llm"]["provider"] == "anthropic"
    assert parsed["agent"]["max_steps"] == 20


# 功能：CRLF 文件里新插入的行也用 CRLF（Windows 上不产生混合行尾）
# 设计：混合行尾没有语法错误，但会让 git diff 显示"整文件改动"——这类噪音
#       一旦进入用户的配置仓库，后续每改一行都像重写了全部
def test_upsert_keeps_crlf() -> None:
    text = "[llm]\r\nprovider = \"a\"\r\n"
    out = upsert_section(text, "llm", {"base_url": "https://x"})

    assert "\r\nbase_url = " in out
    assert "\nbase_url = " not in out.replace("\r\n", "")


# 功能：字符串值按 JSON 转义，引号/反斜杠/换行都能被 tomllib 原样读回
# 设计：base_url 里出现引号是极少数情况，但一旦发生，裸拼字符串会写出非法 TOML
def test_toml_value_escaping() -> None:
    assert toml_value('a"b\\c') == '"a\\"b\\\\c"'
    assert toml_value("a\nb") == '"a\\nb"'
    assert toml_value(True) == "true"
    assert toml_value(128000) == "128000"


# 功能：write_config_sections 落盘后可被 tomllib 解析，且既有内容仍在
# 设计：端到端走一遍"文件不存在 → 建出来"的路径（GUI 首次保存时就是这种状态）
def test_write_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    write_config_sections(path, {"llm": {"default_model": "deepseek-chat"}})

    parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    assert parsed["llm"]["default_model"] == "deepseek-chat"


# 功能：写出的整份文件若解析失败，抛 ConfigWriteError 且磁盘上的原文件不动
# 设计：原文本身就含重复段（用户手误）时，任何真实解析都会失败——把它当作
#       "回滚路径"的触发器，断言异常类型与磁盘内容都没变，保证坏文件不会更坏
def test_write_rolls_back_on_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    broken = "[llm]\nprovider = \"a\"\n[llm]\nbase_url = \"b\"\n"
    path.write_text(broken, encoding="utf-8")

    with pytest.raises(ConfigWriteError):
        write_config_sections(path, {"llm": {"default_model": "m"}})

    assert path.read_text(encoding="utf-8") == broken


# 功能：目标路径不可写时抛 ConfigWriteError（而不是半截文件后静默返回）
# 设计：父路径是文件 → mkdir 必失败；GUI 需要把"写不进去"如实报给用户
def test_write_reports_io_failure(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")

    with pytest.raises(ConfigWriteError):
        write_config_sections(blocker / "config.toml", {"llm": {"provider": "anthropic"}})
