"""生成型工具的配额守门测试

【为什么单列一个文件】`write_file` / `edit_*` 的配额已有覆盖，但生成型工具
（docs / README / CHANGELOG / skill / tests）历史上直接 `write_text`，是配额
最容易漏的一圈。这里用"极小配额 + 真实工具调用"把注入点钉住：只要谁把
`check_write_quota` 删掉，测试立刻红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from iwan_claude.core.config import SandboxConfig
from iwan_claude.core.sandbox import init_sandbox
from iwan_claude.core.tools.builtin.documentation import (
    ChangelogTool,
    GenerateDocsTool,
    UpdateReadmeTool,
)
from iwan_claude.core.tools.builtin.testing import GenerateTestsTool


# 功能：把沙箱根指向临时目录，并把总配额压到几乎为零
# 设计：所有生成工具都写相对路径，必须先 chdir 到沙箱根，否则 validate_path 会
#       因"路径越界"先失败——那样测到的是路径校验，不是配额，断言就失去针对性
@pytest.fixture()
def tiny_quota_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    init_sandbox(
        SandboxConfig(enabled=True, root=str(tmp_path), max_total_size=1, max_file_size=1_000_000)
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


# 功能：generate_docs 在总配额超限时返回 is_error，且不落盘
# 设计：配额设为 1 字节，生成内容必然超过；断言 is_error 与"文件不存在"两个事实，
#       后者能区分"只在返回里报错但文件仍写了"这种假修
async def test_generate_docs_respects_quota(tiny_quota_sandbox: Path) -> None:
    result = await GenerateDocsTool().invoke({"source_path": "src", "output_path": "docs"})
    assert result.is_error
    assert "quota" in result.content.lower()
    assert not (tiny_quota_sandbox / "docs" / "index.md").exists()


# 功能：update_readme 在总配额超限时返回 is_error，不创建/不改 README
# 设计：README 不存在 → 会先走"建默认文件"那条分支，正好同时覆盖该处的配额检查
async def test_update_readme_respects_quota(tiny_quota_sandbox: Path) -> None:
    result = await UpdateReadmeTool().invoke({"content": "hello"})
    assert result.is_error
    assert "quota" in result.content.lower()
    assert not (tiny_quota_sandbox / "README.md").exists()


# 功能：changelog 工具在总配额超限时返回 is_error
# 设计：走 add 分支（写入条目），覆盖"读旧内容→拼新内容→写回"这条最容易漏检的路径
async def test_changelog_respects_quota(tiny_quota_sandbox: Path) -> None:
    result = await ChangelogTool().invoke({"message": "init release", "type": "feature"})
    assert result.is_error
    assert "quota" in result.content.lower()
    assert not (tiny_quota_sandbox / "CHANGELOG.md").exists()


# 功能：generate_tests 在总配额超限时返回 is_error，且不写测试文件
# 设计：显式给 output_path，避免它去猜默认 tests/ 目录；断言目标文件不存在，
#       确保配额失败发生在写入之前而不是写完之后
async def test_generate_tests_respects_quota(tiny_quota_sandbox: Path) -> None:
    target = tiny_quota_sandbox / "src" / "mod.py"
    result = await GenerateTestsTool().invoke(
        {"file_path": str(target), "output_path": "test_mod.py"}
    )
    assert result.is_error
    assert "quota" in result.content.lower()
    assert not (tiny_quota_sandbox / "test_mod.py").exists()
