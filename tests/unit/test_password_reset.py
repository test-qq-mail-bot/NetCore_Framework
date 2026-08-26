"""tests/unit/test_password_reset.py - password_plain 改密链路回归（审查需求）

验证：
1. 默认生成的 user_config.yaml 不含 password_plain 行（不再无条件输出空行）；
2. 用户手动添加 auth.password_plain 后，重启触发 _check_password_reset：
   - password_hash 更新为新密码的 PBKDF2-SHA256 哈希；
   - password_plain 从内存与文件中自动删除；
   - TOTP 一并重置；
   - 进程退出（SystemExit）。
"""
import pytest
import yaml


def _auth_sec(text: str) -> str:
    """截取 auth: 段（auth: 到 password_hash 之间）。"""
    return text.split("auth:")[1].split("password_hash")[0]


def test_default_render_no_password_plain_line(isolated_env):
    """默认渲染不应包含 password_plain 行（但提示注释保留）。"""
    import core.config_loader as cl
    cl.bootstrap()
    text = (cl.CONFIG_DIR / "user_config.yaml").read_text(encoding="utf-8")
    assert "password_plain" not in _auth_sec(text)
    assert "如何修改登录密码" in text
    assert "password_hash" in text
    yaml.safe_load(text)  # 必须可解析


def test_password_plain_auto_reset_and_remove(isolated_env):
    """手动添加 password_plain → 重置哈希 → 自动删除该行 → 退出。"""
    import core.config_loader as cl
    from core.crypto_utils import CryptoUtils
    cl.bootstrap()
    p = cl.CONFIG_DIR / "user_config.yaml"

    # 模拟用户手动添加改密请求
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["auth"]["password_plain"] = "NewPass@456"
    cl.save_user_config(data)
    text2 = p.read_text(encoding="utf-8")
    assert "password_plain" in _auth_sec(text2)
    yaml.safe_load(text2)

    # 触发启动期重置（期望 SystemExit 退出）
    from core.framework import _check_password_reset
    with pytest.raises(SystemExit):
        _check_password_reset()

    text3 = p.read_text(encoding="utf-8")
    data3 = yaml.safe_load(text3)
    assert "password_plain" not in data3.get("auth", {})
    assert "password_plain" not in _auth_sec(text3)
    assert CryptoUtils.verify_password("NewPass@456", data3["auth"]["password_hash"])
    assert data3["auth"].get("totp_enabled") is False
    assert data3["auth"].get("totp_secret", "") == ""
