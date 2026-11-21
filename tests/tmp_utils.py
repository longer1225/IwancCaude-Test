"""测试临时目录的唯一入口（所有 mkdtemp 都必须经过这里）

【为什么要统一】
1. `tempfile.mkdtemp()` 在系统临时目录不可写时会**退回到 cwd**（沙箱/受限 CI 里很常见）。
   于是 `iwan_daemon_*` / `iwan_authd_*` 会撒在仓库根——实测堆了近百个目录。
2. 散落在系统 temp 里的目录也没人回收：daemon 启动失败的用例在 `yield` 之前就
   `pytest.fail`，清理代码根本不执行。

【约定】全部落到 `runs/tmp/`（`runs/` 已被 .gitignore 忽略），夹具用 finalizer 清理，
失败路径也不漏。需要换位置时设 `IWAN_TEST_TMP`。
"""
from __future__ import annotations

import os
from pathlib import Path

# 仓库根：tests/tmp_utils.py → parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tmp_root() -> Path:
    """返回测试临时根（默认 <repo>/runs/tmp，可用 IWAN_TEST_TMP 覆盖），并确保存在"""
    raw = os.environ.get("IWAN_TEST_TMP", "").strip()
    root = Path(raw).expanduser() if raw else _REPO_ROOT / "runs" / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root
