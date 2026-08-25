"""
security.py - 安全模块

功能：IP 黑白名单校验、登录失败策略与自动封禁

设计依据（项目书 §9.1）：检查顺序 白名单 → 黑名单(404) → 正常登录。
- 白名单：受信任 IP（如管理员来源 IP），**放行且不参与失败锁定策略**，
  并非「仅白名单可访问」的防火墙模式。这样既避免管理员因多次输错密码被锁，
  也不会误伤其他正常用户的访问。
- 黑名单：命中且在封禁期内（含手动永久封禁）则拒绝访问（返回 404 以隐藏存在）。
- 每个条目均可携带说明(note)与有效期(expires_at)，过期条目自动失效。
"""
import ipaddress
import threading
import time
from datetime import datetime, timezone

from core.config_loader import get_security_config, save_security_config
from core.logger import get_logger

logger = get_logger()


def _entry_ip(entry) -> str:
    """从白/黑名单条目中取 IP 字符串（兼容 旧版纯字符串 / 新版字典）"""
    if isinstance(entry, dict):
        return str(entry.get("ip", "")).strip()
    return str(entry).strip()


def _ip_match(ip: str, items: list):
    """判断 IP 是否命中给定的 IP / CIDR 列表，返回命中的条目（dict 或 str），未命中返回 None。

    支持：CIDR 网段、精确 IP、非标准字符串精确匹配。
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for item in items:
        entry_ip = _entry_ip(item)
        if not entry_ip:
            continue
        try:
            if "/" in entry_ip:
                if addr in ipaddress.ip_network(entry_ip, strict=False):
                    return item
            elif addr == ipaddress.ip_address(entry_ip):
                return item
        except ValueError:
            # 非标准格式则按字符串精确匹配
            if ip == entry_ip:
                return item
    return None


def _parse_dt(value):
    """将 ISO8601 字符串解析为带时区的 datetime（无时区则按 UTC 处理）"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return None


def _is_expired(entry) -> bool:
    """条目是否已超过有效期（expires_at，ISO8601；为空表示永久有效）"""
    if not isinstance(entry, dict):
        return False
    exp = entry.get("expires_at")
    if not exp:
        return False
    until = _parse_dt(exp)
    if until is None:
        return False
    return until < datetime.now(timezone.utc)


class SecurityManager:
    """安全管理器（单例），负责黑白名单与失败策略"""

    def __init__(self):
        # ip -> (连续失败次数, 最后一次失败的时间戳)
        # 仅存于内存，进程重启即清零；封禁结果才落盘到 security.yaml 的 blacklist
        self._failures = {}
        self._lock = threading.Lock()

    def check_ip(self, ip: str) -> tuple:
        """
        检查 IP 访问权限。

        返回值只有两种：("allow", None) 或 ("deny_blacklist", 404)。
        白名单是「受信任放行 + 免失败锁定」，不是「仅白名单可访问」的防火墙，
        因此**不会**返回 deny_whitelist；调用方（framework.security_middleware）
        也不应再为该值保留分支。
        """
        cfg = get_security_config()
        # 安全兜底：回环地址（本地管理通道）永远放行，
        # 避免管理员因白名单配置错误（如只加了某远端 IP）而把自己锁在门外。
        if ip in ("127.0.0.1", "::1") or ip.startswith("127."):
            return ("allow", None)

        # 1) 白名单：受信任 IP 直接放行（且免锁定，见 record_failure）
        wl_match = _ip_match(ip, cfg.get("whitelist", []) or [])
        if wl_match is not None and not _is_expired(wl_match):
            return ("allow", None)

        # 2) 黑名单：封禁期内拒绝（返回 404 以隐藏存在）
        for entry in cfg.get("blacklist", []) or []:
            if _entry_ip(entry) != ip:
                continue
            if _is_expired(entry):
                continue
            block_until = entry.get("block_until")
            if block_until:
                until = _parse_dt(block_until)
                if until is not None and until > datetime.now(timezone.utc):
                    return ("deny_blacklist", 404)
            else:
                # 无 block_until（手动永久封禁）且未过期 → 拒绝
                return ("deny_blacklist", 404)

        # 3) 正常登录（受失败策略约束）
        return ("allow", None)

    def is_whitelist_exempt(self, ip: str) -> bool:
        """该 IP 是否属于白名单（受信任、免锁定）且未过期"""
        wl_match = _ip_match(ip, get_security_config().get("whitelist", []) or [])
        return wl_match is not None and not _is_expired(wl_match)

    def record_failure(self, ip: str) -> bool:
        """
        记录一次登录失败，达到阈值则加入黑名单。
        返回是否触发封禁。
        白名单（受信任）IP 免除锁定策略。
        """
        # 受信任 IP 不参与失败计数
        if self.is_whitelist_exempt(ip):
            return False
        cfg = get_security_config()
        policy = cfg.get("failure_policy", {}) or {}
        max_failures = policy.get("max_failures", 5)
        block_minutes = policy.get("block_minutes", 10)
        # 导致失败计数永不衰减：几个月里零星输错几次密码也会累计到阈值而被误封。
        reset_interval = int(policy.get("reset_interval_minutes", 30) or 0)
        now = time.time()
        with self._lock:
            count, last_ts = self._failures.get(ip, (0, 0.0))
            if reset_interval > 0 and last_ts and (now - last_ts) > reset_interval * 60:
                count = 0
            count += 1
            self._failures[ip] = (count, now)
            if count >= max_failures:
                self._add_blacklist(ip, block_minutes, "连续%d次失败" % count)
                # 已封禁，计数清空；解封后重新累计
                self._failures.pop(ip, None)
                return True
        return False

    def reset_failures(self, ip: str):
        """登录成功后清空该 IP 的失败计数"""
        with self._lock:
            self._failures.pop(ip, None)

    def _add_blacklist(self, ip: str, block_minutes: int, reason: str,
                       note: str = "", expires_at: str = None):
        cfg = get_security_config()
        blacklist = cfg.get("blacklist", []) or []
        # 去重
        blacklist = [e for e in blacklist if _entry_ip(e) != ip]
        block_until = None
        if block_minutes > 0:
            until = datetime.now(timezone.utc).timestamp() + block_minutes * 60
            block_until = datetime.fromtimestamp(until, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        blacklist.append({
            "ip": ip,
            "block_until": block_until,
            "reason": reason,
            "note": note or "",
            "expires_at": expires_at or None,
            "fail_count": 1,
        })
        cfg["blacklist"] = blacklist
        save_security_config(cfg)
        logger.warning("IP %s 已被封禁 %d 分钟：%s", ip, block_minutes, reason)

    def add_whitelist(self, ip: str, note: str = "", expires_at: str = None):
        cfg = get_security_config()
        wl = cfg.get("whitelist", []) or []
        if any(_entry_ip(e) == ip for e in wl):
            raise ValueError("该 IP 已在白名单中，不能重复添加")
        bl = cfg.get("blacklist", []) or []
        if any(_entry_ip(e) == ip for e in bl):
            raise ValueError("该 IP 已在黑名单中，不能同时加入白名单")
        wl.append({"ip": ip, "note": note or "", "expires_at": expires_at or None})
        cfg["whitelist"] = wl
        save_security_config(cfg)

    def remove_whitelist(self, ip: str):
        cfg = get_security_config()
        cfg["whitelist"] = [e for e in (cfg.get("whitelist", []) or []) if _entry_ip(e) != ip]
        save_security_config(cfg)

    def add_blacklist(self, ip: str, minutes: int = 0, reason: str = "手动添加",
                      note: str = "", expires_at: str = None):
        cfg = get_security_config()
        bl = cfg.get("blacklist", []) or []
        if any(_entry_ip(e) == ip for e in bl):
            raise ValueError("该 IP 已在黑名单中，不能重复添加")
        wl = cfg.get("whitelist", []) or []
        if any(_entry_ip(e) == ip for e in wl):
            raise ValueError("该 IP 已在白名单中，不能同时加入黑名单")
        block_until = None
        if minutes > 0:
            until = datetime.now(timezone.utc).timestamp() + minutes * 60
            block_until = datetime.fromtimestamp(until, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bl.append({
            "ip": ip,
            "block_until": block_until,
            "reason": reason,
            "note": note or "",
            "expires_at": expires_at or None,
            "fail_count": 0,
        })
        cfg["blacklist"] = bl
        save_security_config(cfg)

    def remove_blacklist(self, ip: str):
        cfg = get_security_config()
        cfg["blacklist"] = [e for e in (cfg.get("blacklist", []) or []) if _entry_ip(e) != ip]
        save_security_config(cfg)

    def update_failure_policy(self, policy: dict):
        cfg = get_security_config()
        cfg["failure_policy"] = policy
        save_security_config(cfg)


# 全局单例
_security_manager = SecurityManager()


def get_security_manager() -> SecurityManager:
    return _security_manager
