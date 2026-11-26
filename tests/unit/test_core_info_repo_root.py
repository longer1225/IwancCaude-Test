"""仓库根查找语义（BUG-3 的判定依据）

【为什么这条逻辑值得单独测】
GUI 判断"连的是不是本仓库的 daemon"，靠的是双方 **仓库根** 比较：
daemon 侧由 `app._find_repo_root(cwd)` 产出，GUI 侧由 `daemon.findRepoRoot()` 产出。
两边只要有一边把"子目录"当成"仓库根"，比较就永远不相等——结果是正常场景下
也弹"已连接外部 daemon"，最典型的狼来了。

【覆盖点】
1. 就近原则：从深层子目录出发，命中**最近的** .git（不是最外层）
2. `.git` 是文件也算（worktree / submodule 的形态）
3. 起点本身是仓库根时原样返回
"""
from __future__ import annotations

from pathlib import Path

from iwan_claude.core.app import _find_repo_root


# 功能：从深层子目录出发命中最内层的 .git
# 设计：先造 outer/.git 再造 outer/inner/.git，断言返回 inner——
#       若实现成了"一路爬到最外层"，这里会拿到 outer（GUI 就会误判成外部实例）
def test_finds_nearest_git_dir(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "pkg" / "inner"
    deep = inner / "src" / "mod"
    (outer / ".git").mkdir(parents=True)
    (inner / ".git").mkdir(parents=True)
    deep.mkdir(parents=True)

    assert _find_repo_root(deep) == inner.resolve()


# 功能：.git 是普通文件（git worktree / submodule）时同样认定为仓库根
# 设计：`git worktree add` 生成的子工作区里 .git 是一个 text 文件（gitdir: ...）；
#       只判断"是不是目录"会让这类工作区的仓库根识别失败
def test_git_file_also_counts_as_repo_root(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    sub = worktree / "a" / "b"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: C:/somewhere/.git/worktrees/wt\n", encoding="utf-8")
    sub.mkdir(parents=True)

    assert _find_repo_root(sub) == worktree.resolve()


# 功能：起点本身就是仓库根时原样返回
# 设计：daemon 常见形态就是"在仓库根启动"；这条是最高频路径，不能依赖父目录兜底
def test_start_at_repo_root_returns_itself(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert _find_repo_root(tmp_path) == tmp_path.resolve()


# 功能：返回值是绝对路径（客户端要拿它做字符串比较，相对路径会误判）
# 设计：GUI 侧会对两边做规范化后比较，服务端先给绝对路径能少一类"看起来一样其实不同"
def test_returns_absolute_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    got = _find_repo_root(repo / "sub")
    assert got.is_absolute()
    assert got == repo.resolve()
