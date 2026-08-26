"""tests/unit/test_security.py - 安全策略回归：白名单/黑名单/失败计数原子自增"""
import os


def test_loopback_whitelist_initialized(isolated_env):
    """审查报告需求1：初始化时回环 127.0.0.1 / ::1 应自动写入白名单且永久有效。"""
    import core.config_loader as cl
    cl.bootstrap()
    sec = cl.get_security_config()
    wl = sec.get("whitelist", [])
    ips = [w.get("ip") for w in wl]
    assert "127.0.0.1" in ips
    assert "::1" in ips
    for w in wl:
        if w.get("ip") in ("127.0.0.1", "::1"):
            assert w.get("expires_at") in (None, "", "permanent")


def _set_tz(c):
    c.setdefault("system", {})["timezone"] = "Asia/Shanghai"


def test_atomic_write_preserves_yaml(isolated_env):
    """审查报告 #4：原子写入后 YAML 可解析且完整。"""
    import yaml
    import core.config_loader as cl
    cl.bootstrap()
    cl.update_user_config(_set_tz)
    p = cl.CONFIG_DIR / "user_config.yaml"
    assert p.exists()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data["system"]["timezone"] == "Asia/Shanghai"
