"""本机密钥文件（~/.iwan/secrets.env）的单元测试

【被测对象】secret_store：GUI 保存的 key 落盘、注入 os.environ、删除时还原
【为什么值得单独测】这是全项目唯一"明文密钥落盘"的地方——转义错了 key 会被
截断（用户以为保存成功，实际鉴权失败），删错了会连用户自己的环境变量一起抹掉。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from iwan_claude.core import secret_store


# 功能：每个用例都从"空密钥文件 + 干净的相关环境变量"开始，结束后回滚 os.environ
# 设计：secret_store 直接写 os.environ（生产上必须如此），monkeypatch 管不到它——
#       手工快照/还原才能避免一个用例的 key 泄进下一个用例（曾把"缺 key"断言带偏）
@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "secrets.env"
    monkeypatch.setenv("IWAN_SECRETS_FILE", str(path))
    monkeypatch.delenv("IWAN_TEST_KEY", raising=False)
    before = dict(os.environ)
    secret_store._applied.clear()
    try:
        yield path
    finally:
        secret_store._applied.clear()
        for key in set(os.environ) - set(before):
            os.environ.pop(key, None)
        for key, value in before.items():
            os.environ[key] = value


# 功能：set_secret 落盘后 read_secrets 能原样读回，并同时注入 os.environ
# 设计：断言三件事（文件内容/read_secrets/环境变量），因为 GUI 的"测试连接"用
#       os.environ、daemon 重启用文件——两条通道都必须真的拿到同一把 key
def test_set_secret_roundtrip(_isolated: Path) -> None:
    secret_store.set_secret("IWAN_TEST_KEY", "sk-test-abcdef123456")

    assert secret_store.read_secrets()["IWAN_TEST_KEY"] == "sk-test-abcdef123456"
    assert os.environ["IWAN_TEST_KEY"] == "sk-test-abcdef123456"
    assert "IWAN_TEST_KEY=\"sk-test-abcdef123456\"" in _isolated.read_text(encoding="utf-8")


# 功能：含 # 与反斜杠/引号的 key 经引号转义后仍能完整读回
# 设计：dotenv 对裸值会在 # 处截断——不转义就会出现"保存成功但 key 少半截"，
#       这类 bug 只在真实 key 含特殊字符时出现，必须用构造值把它钉死
def test_special_characters_are_escaped(_isolated: Path) -> None:
    weird = 'sk-a#b\\d"e-fghijkl'
    secret_store.set_secret("IWAN_TEST_KEY", weird)

    assert secret_store.read_secrets()["IWAN_TEST_KEY"] == weird
    assert os.environ["IWAN_TEST_KEY"] == weird


# 功能：删除密钥时把 os.environ 还原成"注入前的值"，而不是无脑 pop
# 设计：用户的 Windows 用户级环境变量优先级本来就高；删掉 GUI 里保存的 key
#       只应回到那个值。这里先手放一个旧值，再 set（覆盖）→ delete（还原）
def test_delete_restores_previous_env(_isolated: Path) -> None:
    os.environ["IWAN_TEST_KEY"] = "from-user-env"
    secret_store.set_secret("IWAN_TEST_KEY", "sk-from-gui-1234")
    assert os.environ["IWAN_TEST_KEY"] == "sk-from-gui-1234"

    assert secret_store.delete_secret("IWAN_TEST_KEY") is True
    assert os.environ["IWAN_TEST_KEY"] == "from-user-env"
    assert "IWAN_TEST_KEY" not in secret_store.read_secrets()


# 功能：删除一个本来就不存在的密钥返回 False（幂等，不抛异常）
# 设计：GUI 的"清除"按钮可能被连点两次；第二次必须当成功而不是报错
def test_delete_missing_secret_is_noop(_isolated: Path) -> None:
    assert secret_store.delete_secret("IWAN_TEST_KEY") is False


# 功能：apply_secrets_to_env 用文件里的值覆盖同名环境变量（GUI 显式动作优先）
# 设计：这是本模块与 config.py 四层优先链唯一的偏离点，必须显式测：文件里有
#       就覆盖、文件里没有就完全不动（后者由 test_delete_restores_previous_env 间接覆盖）
def test_apply_secrets_overrides_env(_isolated: Path) -> None:
    os.environ["IWAN_TEST_KEY"] = "stale-env-value"
    secret_store.set_secret("IWAN_TEST_KEY", "sk-fresh-from-gui")
    os.environ["IWAN_TEST_KEY"] = "stale-env-value"  # 模拟 daemon 下次启动时的初始状态

    applied = secret_store.apply_secrets_to_env()

    assert applied == ["IWAN_TEST_KEY"]
    assert os.environ["IWAN_TEST_KEY"] == "sk-fresh-from-gui"


# 功能：密钥值校验拒绝空值、过短值与非 ASCII 字符
# 设计：非 ASCII 会在 httpx 组 header 时抛 UnicodeEncodeError 且不指出字段，
#       原地拦下并给出可读原因，比让 daemon 在 run 中途炸掉好得多
@pytest.mark.parametrize("bad", ["", "short", "sk-中文key-1234", "sk-key\n12345678"])
def test_invalid_values_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        secret_store.validate_secret_value(bad)


# 功能：密钥变量名必须是环境变量形态（大写字母开头，只含大写/数字/下划线）
# 设计：名字会成为 os.environ 的键，也会决定沙箱 scrub 规则是否命中；小写或带
#       连字符的名字等于把 key 留在子进程环境里，必须拒绝
@pytest.mark.parametrize("bad", ["deepseek_key", "1KEY", "KEY-NAME", ""])
def test_invalid_names_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        secret_store.validate_secret_name(bad)


# 功能：key_hint 只回尾 4 位；过短的 key 干脆不给尾号
# 设计：尾号用于"确认我填的是哪一把 key"；短 key 漏出 4 位=漏出大半，宁可不显示
def test_key_hint() -> None:
    assert secret_store.key_hint("") == ""
    assert secret_store.key_hint("sk-1234567890abcd") == "…abcd"
    assert secret_store.key_hint("abc") == ""
