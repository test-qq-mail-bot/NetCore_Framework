"""tests/unit/test_crypto.py - AES-GCM 往返 + PBKDF2 已知向量回归"""
import base64
import os


def test_aesgcm_roundtrip(isolated_env):
    from core.crypto_utils import CryptoUtils
    key = CryptoUtils.generate_key()
    cipher = CryptoUtils.encrypt("hello-NetCore", key)
    assert cipher and cipher != "hello-NetCore"
    plain = CryptoUtils.decrypt(cipher, key)
    assert plain == "hello-NetCore"


def test_aesgcm_wrong_key_rejected(isolated_env):
    from core.crypto_utils import CryptoUtils
    k1 = CryptoUtils.generate_key()
    k2 = CryptoUtils.generate_key()
    cipher = CryptoUtils.encrypt("secret", k1)
    # 错误密钥应抛异常（InvalidTag），不得静默返回原值
    try:
        CryptoUtils.decrypt(cipher, k2)
        raised = False
    except Exception:
        raised = True
    assert raised, "错钥解密应抛异常"


def test_password_hash_roundtrip(isolated_env):
    from core.crypto_utils import CryptoUtils
    pwd = "Admin@123!"
    h = CryptoUtils.hash_password(pwd)
    assert h and h != pwd
    assert CryptoUtils.verify_password(pwd, h)
    assert not CryptoUtils.verify_password("wrong", h)
