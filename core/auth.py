"""
auth.py - 认证模块

功能：密码 + TOTP 双因素登录、JWT 签发、登录上下文管理
凭证在传输过程中使用 AES-256-GCM 加密，服务端解密后校验
"""
import base64
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone

import pyotp
import qrcode
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.audit import audit_log, ctx_client_ip, ctx_username
from core.config_loader import (
    DATA_DIR,
    get_core_config,
    get_encryption_key,
    get_user_config,
    save_user_config,
)
from core.crypto_utils import CryptoUtils
from core.logger import get_logger
from core.session import get_session_manager

logger = get_logger()
_bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# 极简 JWT（HS256）实现，避免额外依赖
# ------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _jwt_encode(payload: dict, secret: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = ("%s.%s" % (header, body)).encode("utf-8")
    sig = _b64url(_hmac(signing_input, secret))
    return "%s.%s.%s" % (header, body, sig)


def _hmac(data: bytes, secret: str) -> bytes:
    import hashlib
    import hmac

    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()


def _jwt_decode(token: str, secret: str) -> dict:
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
    except ValueError:
        raise ValueError("token 格式错误")
    signing_input = ("%s.%s" % (header_b64, body_b64)).encode("utf-8")
    expected = _b64url(_hmac(signing_input, secret))
    if not _constant_time_equal(expected, sig_b64):
        raise ValueError("签名校验失败")
    payload = json.loads(_b64url_decode(body_b64))
    if "exp" in payload and payload["exp"] < time.time():
        raise ValueError("token 已过期")
    return payload


def _constant_time_equal(a: str, b: str) -> bool:
    import hmac as _hmac_mod

    return _hmac_mod.compare_digest(a, b)


# JWT 签名密钥必须是**稳定来源**：
# 旧实现在每个进程启动时随机生成一个临时分量拼进密钥，导致
#   ① 多 worker 部署时，A 进程签发的 token 到 B 进程校验签名失败；
#   ② 热重载 / 崩溃重启后所有在线会话立即失效；
# 表现为用户随机收到 401 而被踢回登录页。
# 取值优先级（一次解析后缓存，运行期不再变化）：
#   1) config/core.yaml 的 jwt.secret_key（首次生成配置时写入，推荐）；
#   2) 缺失时回退 data/.secret_key：首次访问生成并持久化，之后每次读取同一值。
# 密钥内容与 token 格式（HS256 三段式）均未改变，旧 token 只要密钥一致仍可校验。
_SECRET_KEY_FILE = DATA_DIR / ".secret_key"
_jwt_secret_cache = None
_jwt_secret_lock = threading.Lock()


def _load_persisted_secret() -> str:
    """读取 data/.secret_key；不存在则生成一次并持久化（尽量收紧文件权限）。"""
    try:
        if _SECRET_KEY_FILE.exists():
            value = _SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
            if value:
                return value
    except OSError as exc:
        logger.warning("读取 JWT 密钥文件失败：%s", exc)
    value = secrets.token_hex(32)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _SECRET_KEY_FILE.write_text(value, encoding="utf-8")
        # 仅属主可读写；Windows 上 chmod 语义有限，失败不影响功能
        os.chmod(_SECRET_KEY_FILE, 0o600)
    except OSError as exc:
        logger.warning("持久化 JWT 密钥失败，本次运行使用内存密钥（重启后会话失效）：%s", exc)
    return value


def _jwt_secret() -> str:
    """获取用于 HS256 签名/校验的密钥（进程内缓存，保证签发与校验一致）"""
    global _jwt_secret_cache
    if _jwt_secret_cache:
        return _jwt_secret_cache
    with _jwt_secret_lock:
        if not _jwt_secret_cache:
            configured = (get_core_config().get("jwt", {}) or {}).get("secret_key", "") or ""
            _jwt_secret_cache = configured.strip() or _load_persisted_secret()
    return _jwt_secret_cache


# ------------------------------------------------------------------
# 认证核心逻辑
# ------------------------------------------------------------------
def create_token(username: str) -> str:
    """为指定用户签发 JWT"""
    secret = _jwt_secret()
    expire = get_core_config().get("jwt", {}).get("expire_minutes", 1440)
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + expire * 60,
    }
    return _jwt_encode(payload, secret)


def decode_token(token: str) -> dict:
    """解码并校验 JWT，失败抛出异常"""
    secret = _jwt_secret()
    return _jwt_decode(token, secret)


def decrypt_field(value: str) -> str:
    """使用框架密钥解密前端传来的加密字段"""
    if not value:
        return ""
    # 形态预判：仅当值像密文（合法 base64 且至少 nonce12 + tag16 + 1 字节）才尝试解密。
    # 明文（用户名/密码直传，如纯明文登录链路或测试）直接按明文返回，
    # 不产生「Invalid base64 / Nonce」这类误导性告警。
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:  # noqa: BLE001
        return value
    if len(raw) < 28:
        return value
    try:
        return CryptoUtils.decrypt(value, get_encryption_key())
    except Exception as exc:  # noqa: BLE001
        # 兼容未加密的明文（便于调试/测试）：仍然回退，但必须留痕。
        # 若前端加密链路损坏或 crypto.encryption_key 与前端不一致，
        # 静默回退会让凭证以明文进入业务流程而无人察觉，因此记录告警。
        logger.warning(
            "字段解密失败，已按明文处理（请检查前端加密与 core.yaml 的 crypto.encryption_key 是否一致）：%s",
            exc,
        )
        return value


def authenticate(username: str, password: str, totp_code: str = None) -> dict:
    """
    校验用户凭证。
    返回 {"success": bool, "token": str, "totp_required": bool, "message": str}
    """
    user_cfg = get_user_config().get("auth", {})
    real_username = user_cfg.get("username", "admin")

    if username != real_username:
        audit_log("login_attempt", "用户名不存在: %s" % username, "failed")
        return {"success": False, "message": "用户名或密码错误"}

    if not CryptoUtils.verify_password(password, user_cfg.get("password_hash", "")):
        audit_log("login_attempt", "密码错误", "failed", username=username)
        return {"success": False, "message": "用户名或密码错误"}

    # TOTP 校验
    if user_cfg.get("totp_enabled"):
        secret = user_cfg.get("totp_secret", "")
        if not secret:
            return {"success": False, "message": "TOTP 未正确绑定"}
        # secret 可能为加密存储
        try:
            secret = CryptoUtils.decrypt(secret, get_encryption_key())
        except Exception:  # noqa: BLE001
            pass
        if not totp_code or not pyotp.TOTP(secret).verify(totp_code, valid_window=1):
            audit_log("login_attempt", "TOTP 校验失败", "failed", username=username)
            return {"success": False, "message": "TOTP 验证码错误", "totp_required": True}

    token = create_token(real_username)
    # 记录上次登录信息
    new_cfg = get_user_config()
    new_cfg.setdefault("auth", {})["last_login_time"] = datetime.now(timezone.utc).isoformat()
    new_cfg["auth"]["last_login_ip"] = ctx_client_ip.get() or "127.0.0.1"
    save_user_config(new_cfg)
    audit_log("login_attempt", "登录成功", "success", username=username)
    return {"success": True, "token": token, "totp_required": bool(user_cfg.get("totp_enabled")),
            "message": "登录成功"}


def setup_totp(username: str) -> dict:
    """生成 TOTP 密钥与二维码，供前端绑定。

    生成的密钥在服务端以 pending_totp_secret（加密）暂存，verify_totp 仅校验
    该待绑定密钥，杜绝前端回传任意 secret 绑定到自己掌控的密钥（越权绑定）。
    """
    secret = pyotp.random_base32()
    system = get_core_config().get("system", {})
    name = get_user_config().get("system", {}).get("name") or "NetCore Framework"
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=name)
    # 服务端暂存待绑定密钥（加密），verify 时强制使用，不接受客户端传入的 secret
    try:
        cfg = get_user_config()
        cfg.setdefault("auth", {})["pending_totp_secret"] = CryptoUtils.encrypt(secret, get_encryption_key())
        save_user_config(cfg)
    except Exception:  # noqa: BLE001
        pass
    # 生成二维码（纯 Python SVG，无需 Pillow 依赖）
    import io

    from qrcode.image.svg import SvgImage

    img = qrcode.make(uri, image_factory=SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    qr_svg = buf.getvalue().decode("utf-8")
    qr_b64 = base64.b64encode(qr_svg.encode("utf-8")).decode("utf-8")
    return {"secret": secret, "otpauth_uri": uri, "qrcode": qr_b64, "qrcode_type": "svg"}


def verify_totp(code: str, secret: str = None) -> bool:
    """校验 TOTP 绑定验证码，成功则写入用户配置。

    安全：优先使用 setup_totp 阶段服务端暂存的 pending_totp_secret，忽略客户端
    传入的 secret；仅当无服务端暂存（兼容旧流程/测试）才回退客户端 secret。
    """
    cfg = get_user_config()
    pending = (cfg.get("auth", {}) or {}).get("pending_totp_secret")
    if pending:
        try:
            use_secret = CryptoUtils.decrypt(pending, get_encryption_key())
        except Exception:  # noqa: BLE001
            use_secret = secret
    else:
        # 兼容旧流程：无服务端暂存时回退客户端传入（不推荐）
        use_secret = secret
    if not use_secret:
        return False
    try:
        if not pyotp.TOTP(use_secret).verify(code, valid_window=1):
            return False
    except Exception:  # noqa: BLE001
        return False
    encrypted_secret = CryptoUtils.encrypt(use_secret, get_encryption_key())
    auth = cfg.setdefault("auth", {})
    auth["totp_secret"] = encrypted_secret
    auth["totp_enabled"] = True
    auth.pop("pending_totp_secret", None)
    save_user_config(cfg)
    audit_log("totp_bind", "TOTP 绑定成功", "success", username=cfg.get("auth", {}).get("username"))
    return True


async def get_current_user(request: Request, cred: HTTPAuthorizationCredentials = Depends(_bearer)):
    """
    FastAPI 依赖：校验 JWT 并返回当前用户名，
    同时把用户名与客户端 IP 注入审计上下文。
    """
    if cred is None or not cred.credentials:
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    try:
        payload = decode_token(cred.credentials)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="凭证无效或已过期")
    # 会话空闲超时校验：前端心跳或有效操作会续期，超时则强制失效
    if get_session_manager().touch(cred.credentials):
        raise HTTPException(status_code=401, detail="登录已超时，请重新登录")
    username = payload.get("sub", "system")
    # 注入审计上下文
    ctx_username.set(username)
    client_ip = request.client.host if request.client else "127.0.0.1"
    ctx_client_ip.set(client_ip)
    return username
