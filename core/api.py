"""
api.py - 框架全部 REST API 路由

包含：认证 / 安全 / 通知 / 审计 / 系统 / 插件 六组路由
"""
import asyncio
import csv
import io
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.audit import audit_log, clean_audit, query_audit
from core.auth import (
    authenticate,
    decode_token,
    get_current_user,
    setup_totp,
    verify_totp,
)
from core.config_loader import (
    get_core_config,
    get_security_config,
    get_system_info,
    get_transport_encryption_key,
    get_user_config,
    save_security_config,
)
from core.crypto_utils import CryptoUtils
from core.logger import get_logger, set_level, get_level
from core.notify import get_notify_manager
from core.plugin_manager import get_plugin_manager
from core.security import get_security_manager
from core.session import get_session_manager

logger = get_logger()

router_auth = APIRouter()
router_security = APIRouter()
router_notify = APIRouter()
router_audit = APIRouter()
router_system = APIRouter()
router_plugins = APIRouter()


def _extract_bearer(request: Request) -> str:
    """从 Authorization 头提取 Bearer token（无则返回空串）"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1)
    return ""


# ==================================================================
# 认证
# ==================================================================
class LoginRequest(BaseModel):
    username: str
    password: str          # AES-256-GCM 加密后的密文（Base64）
    totp: str = None       # AES-256-GCM 加密后的 TOTP 验证码（可选）


class TotpVerifyRequest(BaseModel):
    code: str
    secret: str = ""


# 默认密码判定结果按 password_hash 缓存：PBKDF2 校验一次约数百毫秒，
# 此前每次成功登录都重算一遍（纯浪费，哈希不变结果不变）。
_default_pw_cache: dict = {}
_default_pw_lock = threading.Lock()


def _is_default_password(password_hash: str) -> bool:
    """判断当前密码哈希是否对应默认密码 Admin@123!（供前端改密提示）。"""
    if not password_hash:
        return False
    with _default_pw_lock:
        cached = _default_pw_cache.get(password_hash)
    if cached is None:
        cached = CryptoUtils.verify_password("Admin@123!", password_hash)
        with _default_pw_lock:
            _default_pw_cache[password_hash] = cached
    return cached


@router_auth.post("/auth/login")
async def auth_login(req: LoginRequest, request: Request):
    from core.auth import decrypt_field
    from core.security import get_security_manager
    from core.session import get_session_manager

    client_ip = request.client.host if request.client else "127.0.0.1"
    # 安全模块：IP 黑名单/白名单已在中间件处理，这里仅处理失败策略
    username = decrypt_field(req.username)
    password = decrypt_field(req.password)
    totp = decrypt_field(req.totp) if req.totp else None

    # 审查修复：authenticate 内含 PBKDF2（600k 迭代，数百毫秒 CPU），此前在事件
    # 循环内同步执行，并发登录会卡住整个服务。转线程池执行。
    result = await asyncio.to_thread(authenticate, username, password, totp)
    if not result["success"]:
        # 记录失败策略
        sec = get_security_manager()
        blocked = sec.record_failure(client_ip)
        if blocked:
            return {"success": False, "message": "登录失败次数过多，IP 已被临时封禁"}
        return {"success": False, "message": result["message"], "totp_required": result.get("totp_required", False)}
    get_security_manager().reset_failures(client_ip)
    get_session_manager().create(result["token"])
    # 是否为默认密码（用于前端提示；带缓存 + 线程池，见 _is_default_password）
    is_default = await asyncio.to_thread(
        _is_default_password, get_user_config().get("auth", {}).get("password_hash", ""))
    return {
        "success": True,
        "token": result["token"],
        "totp_required": result.get("totp_required", False),
        "username": username,
        "is_default_password": is_default,
    }


@router_auth.post("/auth/totp/setup")
async def auth_totp_setup(_: str = Depends(get_current_user)):
    user = get_user_config().get("auth", {}).get("username", "admin")
    return setup_totp(user)


@router_auth.post("/auth/totp/verify")
async def auth_totp_verify(req: TotpVerifyRequest, _: str = Depends(get_current_user)):
    ok = verify_totp(req.code, getattr(req, "secret", None))
    if not ok:
        return {"success": False, "message": "验证码错误"}
    return {"success": True, "message": "TOTP 绑定成功"}


@router_auth.post("/auth/logout")
async def auth_logout(request: Request, _: str = Depends(get_current_user)):
    token = _extract_bearer(request)
    if token:
        get_session_manager().remove(token)
    audit_log("logout", "用户注销", "success")
    return {"success": True, "message": "已注销"}


@router_auth.post("/auth/heartbeat")
async def auth_heartbeat(request: Request, _: str = Depends(get_current_user)):
    """前端节流心跳：每次调用都会经过 get_current_user 自动续期会话。
    返回剩余有效秒数（-1 表示已关闭自动退出）。
    """
    token = _extract_bearer(request)
    return {"success": True, "remaining_seconds": get_session_manager().remaining(token)}


# ==================================================================
# 安全
# ==================================================================
class WhitelistItem(BaseModel):
    ip: str
    note: str = ""
    expires_at: str = None


class BlacklistItem(BaseModel):
    ip: str
    # 审查修复：此前 minutes 由裸 int(item.get("minutes") or 0) 解析，
    # 非法输入直接 500；交由 Pydantic 统一校验（负数/非整数 → 422）
    minutes: int = Field(default=0, ge=0, le=1000000)
    note: str = ""
    expires_at: str = None


class FailurePolicyRequest(BaseModel):
    """登录失败策略（审查修复：此前接受任意 dict 整体覆盖 failure_policy，
    塞入非法值后 record_failure 比较时抛 TypeError 导致登录链路 500）。"""
    max_failures: int = Field(default=5, ge=1, le=10000)
    block_minutes: int = Field(default=10, ge=0, le=1000000)
    reset_interval_minutes: int = Field(default=30, ge=0, le=1000000)


@router_security.get("/security/whitelist")
async def sec_get_whitelist(_: str = Depends(get_current_user)):
    return get_security_config().get("whitelist", [])


@router_security.post("/security/whitelist")
async def sec_add_whitelist(item: WhitelistItem, _: str = Depends(get_current_user)):
    if not item.ip.strip():
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少 ip"})
    try:
        get_security_manager().add_whitelist(
            item.ip.strip(), note=item.note, expires_at=item.expires_at)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    audit_log("security_policy_changed", "添加白名单:%s" % item.ip, "success")
    return {"success": True}


@router_security.delete("/security/whitelist")
async def sec_del_whitelist(ip: str = Query(...), _: str = Depends(get_current_user)):
    get_security_manager().remove_whitelist(ip)
    audit_log("security_policy_changed", "删除白名单:%s" % ip, "success")
    return {"success": True}


@router_security.get("/security/blacklist")
async def sec_get_blacklist(_: str = Depends(get_current_user)):
    return get_security_config().get("blacklist", [])


@router_security.post("/security/blacklist")
async def sec_add_blacklist(item: BlacklistItem, _: str = Depends(get_current_user)):
    if not item.ip.strip():
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少 ip"})
    try:
        get_security_manager().add_blacklist(
            item.ip.strip(), item.minutes, "手动添加",
            note=item.note, expires_at=item.expires_at)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    audit_log("security_policy_changed", "添加黑名单:%s" % item.ip, "success")
    return {"success": True}


@router_security.delete("/security/blacklist")
async def sec_del_blacklist(ip: str = Query(...), _: str = Depends(get_current_user)):
    get_security_manager().remove_blacklist(ip)
    audit_log("security_policy_changed", "删除黑名单:%s" % ip, "success")
    return {"success": True}


@router_security.get("/security/failure-policy")
async def sec_get_policy(_: str = Depends(get_current_user)):
    return get_security_config().get("failure_policy", {})


@router_security.put("/security/failure-policy")
async def sec_put_policy(req: FailurePolicyRequest, _: str = Depends(get_current_user)):
    get_security_manager().update_failure_policy(req.model_dump())
    audit_log("security_policy_changed", "更新失败策略", "success")
    return {"success": True}


# ==================================================================
# 通知
# ==================================================================
@router_notify.post("/notify/send")
async def notify_send(req: dict, _: str = Depends(get_current_user)):
    mgr = get_notify_manager()
    channels = req.get("channels", [])
    results = await asyncio.to_thread(
        mgr.send,
        channels=channels,
        title=req.get("title", ""),
        content=req.get("content", ""),
        priority=req.get("priority", "normal"),
        recipients=req.get("recipients"),
        template_id=req.get("template_id"),
        source=req.get("source", "system"),
        extra=req.get("template_vars"),
    )
    return {"results": results}


@router_notify.get("/notify/channels")
async def notify_channels(_: str = Depends(get_current_user)):
    return {"channels": get_notify_manager().get_channels_status()}


@router_notify.post("/notify/test/{channel}")
async def notify_test(channel: str, req: dict = None, _: str = Depends(get_current_user)):
    recipients = (req or {}).get("recipients") if req else None
    ok, message = await asyncio.to_thread(get_notify_manager().test_channel, channel, recipients)
    return {"success": ok, "message": message}


@router_notify.get("/notify/config")
async def notify_get_config(_: str = Depends(get_current_user)):
    return get_notify_manager().get_config_masked()


@router_notify.put("/notify/config")
async def notify_put_config(req: dict, _: str = Depends(get_current_user)):
    get_notify_manager().save_config(req)
    return {"success": True}


# ==================================================================
# 审计日志
# ==================================================================
@router_audit.get("/logs/audit")
async def audit_query(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=10000),
    ip: str = None,
    result: str = None,
    action: str = None,
    start_date: str = None,
    end_date: str = None,
    sort_by: str = "timestamp_utc",
    sort_order: str = "desc",
    filter_col: str = None,
    filter_values: List[str] = Query(None),
    _: str = Depends(get_current_user),
):
    # 审查修复：query_audit 为全量文件 IO + 内存扫描，此前在事件循环内同步执行，
    # 大日志量时会卡住整个服务。转线程池执行。
    records, total = await asyncio.to_thread(
        query_audit, page=page, size=size, ip=ip, result=result,
        action=action, start_date=start_date, end_date=end_date,
        sort_by=sort_by, sort_order=sort_order,
        filter_col=filter_col, filter_values=filter_values)
    return {"records": records, "total": total, "page": page, "size": size}


# 单次导出的最大条数上限。
# 现改为可配置上限（默认即上限），并在响应头中如实回报总数与截断状态。
AUDIT_EXPORT_MAX = 20000


def _fmt_audit_ts(ts):
    """审计导出用：UTC 时间戳 → 配置时区显示时间（统一实现见 core/timeutil.fmt_utc）。"""
    from core.timeutil import fmt_utc
    return fmt_utc(ts)


@router_audit.get("/logs/audit/export")
async def audit_export(
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    limit: int = Query(AUDIT_EXPORT_MAX, ge=1, le=AUDIT_EXPORT_MAX),
    _: str = Depends(get_current_user),
):
    """导出审计日志（CSV / JSONL）。

    - limit：本次最多导出多少条（1 ~ AUDIT_EXPORT_MAX），默认取上限；
    - 若 total 大于实际导出条数，说明发生截断，响应头 X-Audit-Truncated=true，
      并在内容末尾追加一行截断说明，避免用户误以为拿到的是全量数据；
    - 响应体改为分块生成（generator），不再先在内存里拼出完整字符串。
    """
    import json as _json

    records, total = await asyncio.to_thread(query_audit, page=1, size=limit)
    returned = len(records)
    truncated = total > returned
    headers = {
        "X-Audit-Total": str(total),
        "X-Audit-Returned": str(returned),
        "X-Audit-Truncated": "true" if truncated else "false",
    }
    if truncated:
        logger.warning("审计日志导出被截断：共 %d 条，本次仅导出 %d 条（按最新日期文件优先）", total, returned)

    if fmt == "json":
        headers["Content-Disposition"] = "attachment; filename=audit.jsonl"

        def gen_json():
            for rec in records:
                out = dict(rec)
                # 导出即显示口径：时间换算为配置时区并去 T/Z/毫秒，字段名
                # timestamp_utc 同步更名 timestamp（值不再是 UTC）
                out["timestamp"] = _fmt_audit_ts(out.pop("timestamp_utc", None))
                yield _json.dumps(out, ensure_ascii=False) + "\n"
            if truncated:
                # 以一条元信息记录标注截断，便于下游程序识别
                yield _json.dumps(
                    {"_truncated": True, "total": total, "returned": returned},
                    ensure_ascii=False,
                ) + "\n"

        return StreamingResponse(gen_json(), media_type="application/json", headers=headers)

    # CSV：逐行写入共享缓冲区后立即取出并清空，保证内存占用恒定
    headers["Content-Disposition"] = "attachment; filename=audit.csv"

    def gen_csv():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def flush():
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return data

        # 审查报告 #10：CSV 公式注入消毒——以 = + - @ 开头的单元格前置单引号
        def _csv_safe(v):
            if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
                return "'" + v
            return v

        writer.writerow(["timestamp", "ip", "username", "action", "result", "detail"])
        yield flush()
        for rec in records:
            writer.writerow([_csv_safe(_fmt_audit_ts(rec.get("timestamp_utc"))), _csv_safe(rec.get("ip")),
                             _csv_safe(rec.get("username")), _csv_safe(rec.get("action")),
                             _csv_safe(rec.get("result")), _csv_safe(rec.get("detail"))])
            yield flush()
        if truncated:
            writer.writerow(["# 已截断：共 %d 条，本次仅导出 %d 条" % (total, returned),
                             "", "", "", "", ""])
            yield flush()

    return StreamingResponse(gen_csv(), media_type="text/csv", headers=headers)


@router_audit.delete("/logs/audit/clean")
async def audit_clean(_: str = Depends(get_current_user)):
    count = clean_audit()
    audit_log("audit_clean", "清理审计日志 %d 条" % count, "success")
    return {"success": True, "cleaned": count}


# ==================================================================
# 系统
# ==================================================================
@router_system.get("/system/crypto-key")
async def system_crypto_key():
    """返回**传输派生密钥**（HMAC 派生子密钥），供前端加密登录凭证（AES-256-GCM）；
    同时返回软件名称、版本与 TOTP 开关（公开，供登录页前置展示软件名与 TOTP 输入框）。
    额外返回 builtin_name/builtin_version（**内置**软件名与版本号），
    供浏览器控制台/前端启动日志核对程序新旧（不随用户自定义 name/version 变化）。

    审查修复：本接口无鉴权（登录前必须能取钥），此前直接返回静态主密钥
    crypto.encryption_key，而主密钥还保护落盘的 TOTP secret 与通知密码——等于
    把保险柜密码贴在门口。现改为下发 HMAC 派生的独立传输子密钥（见
    config_loader.get_transport_encryption_key），泄露后无法解密任何落盘密文。
    """
    from core.config_loader import SYSTEM_NAME, SYSTEM_VERSION
    sys_info = get_system_info()
    totp_enabled = bool(get_user_config().get("auth", {}).get("totp_enabled", False))
    return {
        "key": get_transport_encryption_key(),
        "name": sys_info["name"],
        "version": sys_info["version"],
        "builtin_name": SYSTEM_NAME,
        "builtin_version": SYSTEM_VERSION,
        "totp_enabled": totp_enabled,
    }


@router_system.get("/system/health")
async def system_health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@router_system.get("/system/info")
async def system_info(_: str = Depends(get_current_user)):
    import os
    import platform
    import time as _time

    sys_info = get_system_info()
    pm = get_plugin_manager()
    try:
        _hostname = platform.node() or ""
    except Exception:  # noqa: BLE001
        _hostname = ""
    try:
        _cpu = os.cpu_count() or 0
    except Exception:  # noqa: BLE001
        _cpu = 0
    return {
        "name": sys_info["name"],
        "version": sys_info["version"],
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": _hostname,
        "cpu_count": _cpu,
        "pid": os.getpid(),
        "uptime_seconds": int(_time.time() - START_TIME),
        "started_at": datetime.fromtimestamp(START_TIME, timezone.utc).isoformat(),
        "plugin_count": len(pm.plugins),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router_system.get("/system/menus")
async def system_menus(_: str = Depends(get_current_user)):
    return {"menus": get_all_menus()}


@router_system.get("/system/time")
async def system_time(_: str = Depends(get_current_user)):
    """返回系统设置时区的当前时间（含 UTC 对照与偏移）。

    前端所有时间显示统一经本接口获取「配置时区的当前时间」；历史时间戳的本地化
    仍由全局 NC.fmtTime（客户端 Intl 转换）完成，本接口用于需要服务端权威时间的场景。
    """
    from zoneinfo import ZoneInfo
    cfg = get_user_config()
    system = cfg.get("system", {})
    tz_name = system.get("timezone", "Asia/Shanghai") or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz_name = "Asia/Shanghai"
        tz = ZoneInfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    offset = now_local.utcoffset()
    return {
        "timezone": tz_name,
        "local_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "offset_seconds": int(offset.total_seconds()) if offset else 0,
        "offset_hours": round(offset.total_seconds() / 3600, 2) if offset else 0,
    }


@router_system.get("/system/basic-settings")
async def basic_settings_get(_: str = Depends(get_current_user)):
    """获取基础设置：软件名称、版本显示名、TOTP 开关、时区等"""
    cfg = get_user_config()
    system = cfg.get("system", {})
    auth = cfg.get("auth", {})
    return {
        "name": system.get("name", ""),
        "version": system.get("version", ""),
        "totp_enabled": auth.get("totp_enabled", False),
        "auto_logout_minutes": int(system.get("auto_logout_minutes", 5) or 5),
        "timezone": system.get("timezone", "Asia/Shanghai"),
        "auto_update_timezone": bool(system.get("auto_update_timezone", True)),
        "domain": (get_user_config() or {}).get("https", {}).get("domain", ""),
        "https": {
            "enabled": bool(
                (get_user_config() or {}).get("https", {}).get("enabled",
                    (get_core_config() or {}).get("https", {}).get("enabled", True))),
            "auto_redirect": bool(
                (get_user_config() or {}).get("https", {}).get("auto_redirect", True)),
            "custom_uploaded": bool(
                (get_user_config() or {}).get("https", {}).get("cert_content")
                or (get_user_config() or {}).get("https", {}).get("cert_file")),
        },
    }


class BasicSettingsRequest(BaseModel):
    name: str = ""
    version: str = ""
    totp_enabled: bool = False
    auto_logout_minutes: int = 5
    timezone: str = "Asia/Shanghai"
    auto_update_timezone: bool = True
    domain: str = ""


@router_system.put("/system/basic-settings")
async def basic_settings_put(req: BasicSettingsRequest, _: str = Depends(get_current_user)):
    """保存基础设置，实时同步到 user_config.yaml"""
    from core.config_loader import save_user_config
    cfg = get_user_config()
    # 下方直接改 cfg 会同步改动缓存，必须在修改前捕获旧值）
    try:
        _old_sys = dict((cfg.get("system") or {}))
        _old_auth = dict((cfg.get("auth") or {}))
        _old_https = dict((cfg.get("https") or {}))
    except Exception:  # noqa: BLE001
        _old_sys, _old_auth, _old_https = {}, {}, {}
    if "system" not in cfg:
        cfg["system"] = {}
    if "auth" not in cfg:
        cfg["auth"] = {}
    cfg["system"]["name"] = req.name
    cfg["system"]["version"] = req.version
    cfg["auth"]["totp_enabled"] = req.totp_enabled
    # 自动退出时间：0=关闭，正整数=分钟；非法值回退默认 5
    try:
        alm = int(req.auto_logout_minutes)
    except (TypeError, ValueError):
        alm = 5
    if alm < 0:
        alm = 5
    if alm > 1440:
        alm = 1440
    cfg["system"]["auto_logout_minutes"] = alm
    tz = (req.timezone or "Asia/Shanghai").strip()
    if not tz:
        tz = "Asia/Shanghai"
    cfg["system"]["timezone"] = tz
    cfg["system"]["auto_update_timezone"] = bool(req.auto_update_timezone)
    if "https" not in cfg or not isinstance(cfg["https"], dict):
        cfg["https"] = {}
    cfg["https"]["domain"] = req.domain.strip() if isinstance(req.domain, str) else ""
    try:
        diffs = []
        pairs = [
            ("软件名称", _old_sys.get("name", ""), req.name),
            ("软件版本", _old_sys.get("version", ""), req.version),
            ("自动退出时间", _old_sys.get("auto_logout_minutes", 5), alm),
            ("时区", _old_sys.get("timezone", "Asia/Shanghai"), tz),
            ("TOTP", _old_auth.get("totp_enabled", False), bool(req.totp_enabled)),
            ("HTTPS证书SAN地址", _old_https.get("domain", ""), req.domain),
        ]
        for label, ov, nv in pairs:
            if str(ov) != str(nv):
                diffs.append("%s：%s -> %s" % (label, ov, nv))
        if diffs:
            audit_log("basic_settings_updated", "；".join(diffs), "success")
        else:
            audit_log("basic_settings_updated", "基础设置保存（无变化）", "success")
    except Exception:  # noqa: BLE001
        audit_log("basic_settings_updated", "基础设置已保存", "success")
    save_user_config(cfg)
    return {"success": True, "message": "基础设置已保存"}


@router_system.post("/system/https/cert")
async def https_upload_cert(
    cert_file: UploadFile = File(None),
    key_file: UploadFile = File(None),
    _: str = Depends(get_current_user),
):
    """上传自定义 HTTPS 证书与私钥。

    只允许证书（.crt/.pem）与私钥（.key）文件；证书/私钥内容（PEM 文本）直接写入
    user_config.yaml 的 https.cert_content / https.key_content（不再保存文件路径，
    避免文件丢失后 HTTPS 失效），重启服务后生效（uvicorn 以 HTTPS 加载）。
    """
    from core.https_utils import save_uploaded_cert

    cert_ok_ext = (".crt", ".pem")
    key_ok_ext = (".key", ".pem")
    if not cert_file or not key_file:
        return JSONResponse(status_code=400, content={"success": False,
                                                      "message": "请同时上传证书文件与私钥文件"})
    cname = (cert_file.filename or "").lower()
    kname = (key_file.filename or "").lower()
    if not cname.endswith(cert_ok_ext) or not kname.endswith(key_ok_ext):
        return JSONResponse(status_code=400, content={"success": False,
                                                      "message": "证书仅支持 .crt/.pem，私钥仅支持 .key/.pem"})
    # 审查修复：读取无大小上限，超大文件会占满内存。PEM 证书/私钥通常 <20KB，
    # 取 256KB 上限已远超合理范围。优先在 read() 前用 starlette 的 size 元数据拦截
    # （事后检查时内容早已进入内存）；size 缺失时退回读后二次校验。
    _CERT_MAX_BYTES = 256 * 1024
    if (cert_file.size is not None and cert_file.size > _CERT_MAX_BYTES) or \
            (key_file.size is not None and key_file.size > _CERT_MAX_BYTES):
        return JSONResponse(status_code=400, content={"success": False,
                                                      "message": "证书/私钥文件过大（上限 256KB）"})
    cdata = await cert_file.read()
    kdata = await key_file.read()
    if not cdata or not kdata:
        return JSONResponse(status_code=400, content={"success": False,
                                                      "message": "上传内容为空"})
    if len(cdata) > _CERT_MAX_BYTES or len(kdata) > _CERT_MAX_BYTES:
        return JSONResponse(status_code=400, content={"success": False,
                                                      "message": "证书/私钥文件过大（上限 256KB）"})
    try:
        save_uploaded_cert(cdata, kdata)
    except Exception as exc:  # noqa: BLE001
        logger.error("HTTPS 证书保存失败：%s", exc)
        return JSONResponse(status_code=500, content={"success": False,
                                                      "message": "证书保存失败：%s" % exc})
    audit_log("https_cert_uploaded", "证书/私钥已上传（PEM 文本已写入配置），重启后生效", "success")
    return {"success": True, "message": "证书与私钥已上传并写入配置，重启服务后生效"}


@router_system.post("/system/https/switch")
async def https_switch(req: dict, _: str = Depends(get_current_user)):
    """HTTPS 启用开关（写入 user_config，重启生效）。"""
    from core.config_loader import save_user_config
    cfg = get_user_config() or {}
    if "https" not in cfg or not isinstance(cfg["https"], dict):
        cfg["https"] = {}
    cfg["https"]["enabled"] = bool(req.get("enabled", True))
    if "auto_redirect" in req:
        cfg["https"]["auto_redirect"] = bool(req.get("auto_redirect", True))
    save_user_config(cfg)
    audit_log("https_switch", "HTTPS 已%s" % ("启用" if cfg["https"]["enabled"] else "关闭"), "success")
    return {"success": True, "message": "已更新，重启服务后生效"}


@router_system.put("/system/log-level")
async def system_log_level(req: dict, _: str = Depends(get_current_user)):
    """修改日志级别同时**落盘到 user_config.yaml**，
    重启后保持生效（此前只改内存，重启回退 INFO）；并记录修改前后级别到审计日志。"""
    from core.config_loader import save_user_config
    level = (req.get("level", "INFO") or "INFO").upper()
    ok = set_level(level)
    if not ok:
        return {"success": False, "message": "无效的日志级别"}
    try:
        cfg = get_user_config() or {}
        if "logging" not in cfg or not isinstance(cfg["logging"], dict):
            cfg["logging"] = {}
        old = cfg["logging"].get("level", get_level())
        cfg["logging"]["level"] = level
        save_user_config(cfg)
        audit_log("log_level_changed", "日志级别：%s -> %s" % (old, level), "success")
    except Exception as exc:  # noqa: BLE001
        audit_log("log_level_changed", "日志级别调整为 %s（落盘失败：%s）" % (level, exc), "success")
        return {"success": True, "message": "已生效，但写入配置文件失败：%s" % exc}
    return {"success": True}


@router_system.get("/system/log-level")
async def system_log_level_get(_: str = Depends(get_current_user)):
    return {"success": True, "level": get_level()}


@router_system.post("/system/session/reset")
async def system_session_reset(request: Request, _: str = Depends(get_current_user)):
    token = _extract_bearer(request)
    if token:
        get_session_manager().reset(token)
    return {"success": True}


@router_system.get("/system/session/status")
async def system_session_status(request: Request, _: str = Depends(get_current_user)):
    token = _extract_bearer(request)
    return {"remaining_seconds": get_session_manager().remaining(token)}


# ==================================================================
# 插件
# ==================================================================
@router_plugins.get("/plugins/")
async def plugins_status(_: str = Depends(get_current_user)):
    return {"plugins": get_plugin_manager().get_status()}


@router_plugins.post("/plugins/{name}/toggle")
async def plugin_toggle(name: str, req: dict = None, _: str = Depends(get_current_user)):
    """启用/禁用单个插件，持久化到 user_config.yaml 的 plugins.disabled 并重新加载插件。

    - 请求体 {"enabled": true|false}；省略 enabled 则对当前状态取反。
    - plugins.disabled 为空表示启用全部；非空为显式停用列表（被列出的插件将不加载）。
    - 采用「黑名单」语义后，不再存在「全部禁用却被误读为全部启用」的歧义。
    """
    from core.config_loader import save_user_config
    pm = get_plugin_manager()
    cfg = get_user_config()
    if not isinstance(cfg.get("plugins"), dict):
        cfg["plugins"] = {}
    disabled = cfg["plugins"].get("disabled")
    disabled = disabled if isinstance(disabled, list) else []
    current_disabled = set(disabled)  # 必须复制，避免后续操作污染原列表
    target = bool((req or {}).get("enabled")) if (req and "enabled" in req) else (name in current_disabled)
    if target:
        # 启用：从禁用列表移除
        current_disabled.discard(name)
    else:
        # 禁用：加入禁用列表
        current_disabled.add(name)
    cfg["plugins"]["disabled"] = sorted(current_disabled)
    save_user_config(cfg)
    if not target:
        # 审查修复：如实告知限制——Starlette 无法运行期摘除已挂载路由，
        # 禁用插件后其 API 路由保留到下次重启（生命周期已随 load_all 卸载）。
        logger.warning("插件 %s 已禁用：实例已卸载，但其 API 路由需重启服务后才会移除", name)
    try:
        await asyncio.to_thread(pm.load_all)
        # mount_routes 仅在启动 lifespan 执行一次。运行期启用插件后必须补挂路由，
        # 否则出现「插件已启用（菜单出现）但 API 404」的现象（wiki 文档全挂的根因）。
        pm.mount_new_routes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("插件重载失败：%s", exc)
    audit_log(
        "plugin_toggle",
        detail=("启用插件 %s" % name) if target else ("禁用插件 %s" % name),
        result="success",
    )
    return {"success": True, "disabled": cfg["plugins"]["disabled"], "plugin": name, "is_enabled": target}


@router_plugins.post("/system/plugins/reload")
async def plugins_reload(req: dict, _: str = Depends(get_current_user)):
    name = req.get("name")
    if not name:
        return {"success": False, "message": "缺少插件名称"}
    result = await asyncio.to_thread(get_plugin_manager().reload, name)
    audit_log("plugin_reload", detail="重载插件 %s" % name, result="success" if result.get("success") else "failed")
    return result


@router_plugins.post("/system/plugins/reload-all")
async def plugins_reload_all(_: str = Depends(get_current_user)):
    return {"results": await asyncio.to_thread(get_plugin_manager().reload_all)}


@router_plugins.post("/system/plugins/reload-failed")
async def plugins_reload_failed(_: str = Depends(get_current_user)):
    # 审查修复：与 reload/reload-all 保持一致转线程池（含模块导入与 on_load，阻塞 loop）
    return {"results": await asyncio.to_thread(get_plugin_manager().reload_failed)}


# ==================================================================
# 菜单聚合（系统菜单 + 插件菜单）
# ==================================================================
def get_all_menus() -> list:
    # 系统概览（顶部 landing）、插件菜单（中部）、系统设置（固定在最下方）。
    # icon 为前端内置 SVG 图标名称（非 emoji）。
    dashboard = {
        "id": "dashboard",
        "label": "系统概览",
        "icon": "dashboard",
        "path": "/dashboard",
    }
    system_group = {
        "id": "system",
        "label": "系统设置",
        "icon": "setting",
        "children": [
            {"id": "basic-settings", "label": "基础设置", "icon": "setting", "path": "/system/basic-settings"},
            {"id": "security", "label": "安全策略", "icon": "security", "path": "/system/security"},
            {"id": "notify", "label": "通知管理", "icon": "bell", "path": "/system/notify"},
            {"id": "log-center", "label": "日志中心", "icon": "log", "path": "/system/log-center"},
            {"id": "plugins", "label": "插件列表", "icon": "plugin", "path": "/system/plugins"},
        ],
    }
    plugin_menus = get_plugin_manager().get_menus()
    # 插件菜单在前，系统设置固定在最下方（满足"系统设置置于菜单栏最下方"）
    return [dashboard] + plugin_menus + [system_group]


# 启动时间（用于运行时长统计）。审查修复：改用常规导入，
# 替换 `__import__("time").time()` hack 写法。
START_TIME = time.time()
