"""
crypto_utils.py - 通用加密工具模块

功能：提供统一的 AES-256-GCM 加解密、PBKDF2 密码哈希
框架内部及所有插件均可直接调用

密文报文格式（encrypt / decrypt 与前端 frontend/aesgcm.js 严格一致）：
    Base64( nonce[12] || ciphertext[N] || tag[16] )
其中 tag 由 cryptography 的 AESGCM 自动附加在密文尾部，因此拆包时
只需切出前 12 字节 nonce，剩余部分整体交给 aes.decrypt 即可。
未使用 AAD（附加认证数据），三方实现对接时该参数须同样传 None/空。
"""
import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoUtils:
    """通用加密工具类 - 框架及插件均可调用"""

    @staticmethod
    def generate_key() -> str:
        """生成随机 AES-256 密钥，返回 Base64 编码字符串"""
        return base64.b64encode(os.urandom(32)).decode("utf-8")

    @staticmethod
    def encrypt(plaintext: str, key: str) -> str:
        """
        使用 AES-256-GCM 加密明文，返回 Base64 密文（包含 nonce 与 tag）

        参数:
            plaintext: 待加密的明文字符串
            key: Base64 编码的 AES-256 密钥

        返回:
            Base64 编码的 "nonce(12字节) + 密文 + 认证标签(16字节)" 字符串
        """
        if plaintext is None:
            plaintext = ""
        raw_key = base64.b64decode(key)
        aes = AESGCM(raw_key)
        # GCM 的 nonce 必须每次随机且绝不能在同一密钥下重复使用（重复会导致
        # 密钥流复用、认证密钥泄露）；12 字节是 GCM 的标准长度，性能与安全最优。
        nonce = os.urandom(12)
        ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    @staticmethod
    def decrypt(ciphertext: str, key: str) -> str:
        """
        解密 AES-256-GCM 密文，返回明文字符串

        参数:
            ciphertext: Base64 编码的密文（含 nonce）
            key: Base64 编码的 AES-256 密钥

        返回:
            解密后的明文字符串

        说明:
            密钥不匹配、数据被篡改或截断时，AESGCM.decrypt 会抛出 InvalidTag，
            调用方需自行处理（框架内 auth.decrypt_field / notify._decrypt 均会捕获）。
        """
        raw_key = base64.b64decode(key)
        aes = AESGCM(raw_key)
        data = base64.b64decode(ciphertext)
        # 前 12 字节为 nonce，其余为「密文 + 16 字节认证标签」，tag 由库内部校验
        nonce, body = data[:12], data[12:]
        return aes.decrypt(nonce, body, None).decode("utf-8")

    @staticmethod
    def hash_password(password: str) -> str:
        """
        使用 PBKDF2-SHA256 生成密码哈希

        参数:
            password: 明文密码

        返回:
            格式为 "pbkdf2_sha256$迭代次数$盐$哈希" 的字符串
            （迭代次数随哈希一起存储，便于日后调高强度时仍能校验旧密码）
        """
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
        return "pbkdf2_sha256$600000$%s$%s" % (
            base64.b64encode(salt).decode("utf-8"),
            base64.b64encode(dk).decode("utf-8"),
        )

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        验证密码与哈希是否匹配

        参数:
            password: 待验证明文密码
            password_hash: 由 hash_password 生成的哈希字符串

        返回:
            匹配返回 True，否则 False
        """
        try:
            algo, iters, salt_b64, hash_b64 = password_hash.split("$")
            if algo != "pbkdf2_sha256":
                return False
            salt = base64.b64decode(salt_b64)
            # 用哈希串中记录的迭代次数重算，保证与生成时参数一致
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
            # 恒定时间比较：普通 == 会在首个不同字符处提前返回，可被计时攻击逐位试探
            return hmac.compare_digest(base64.b64encode(dk).decode("utf-8"), hash_b64)
        except Exception:
            # 哈希串格式非法/为空（如配置损坏）时一律视为校验失败，绝不放行
            return False
