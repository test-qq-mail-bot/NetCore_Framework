"""
notify.py - 通知管理模块

功能：统一管理邮件、企业微信、钉钉、飞书等通知渠道
提供统一发送 API、Go template 消息模板渲染、发送频率限制
敏感字段（密码、Webhook URL、加签密钥）加密存储
"""
import base64
import hashlib
import hmac
import smtplib
import threading
import urllib.parse
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx

from core.audit import audit_log
from core.config_loader import (
    get_core_config,
    get_encryption_key,
    get_notify_config,
    get_user_config,
    save_notify_config,
)
from core.crypto_utils import CryptoUtils
from core.gotemplate import GoTemplate
from core.logger import get_logger

logger = get_logger()

# 各渠道的敏感字段（保存时需加密，读取时脱敏）
SENSITIVE_FIELDS = {
    "email": ["password"],
    "wechat_work": ["webhook_url"],
    "dingtalk": ["webhook_url", "secret"],
    "feishu": ["webhook_url", "secret"],
}

CHANNEL_NAMES = {
    "email": "邮件",
    "wechat_work": "企业微信",
    "dingtalk": "钉钉",
    "feishu": "飞书",
}

MASK = "********"


def _get_rate_limit_config() -> dict:
    """读取通知频率限制配置： 起 notify 段迁移至 user_config.yaml（可读写），
    此处优先读 user_config，缺失回退 core.yaml（兼容旧实例迁移期）。
    """
    user = get_user_config().get("notify", {}).get("rate_limit", {}) or {}
    core = get_core_config().get("notify", {}).get("rate_limit", {}) or {}
    merged = dict(core)
    merged.update({k: v for k, v in user.items() if v is not None})
    return merged


class NotifyManager:
    """通知管理器（单例）"""

    def __init__(self):
        self.reload()

    def reload(self):
        """重新加载通知配置与加密密钥"""
        self.config = get_notify_config()
        self.key = get_encryption_key()
        self._last_send = {}  # channel -> 上次发送时间戳
        self._lock = threading.Lock()

    # ---------------- 加解密辅助 ----------------
    def _decrypt(self, value):
        """解密敏感字段；失败则原样返回。

        回退是为了兼容用户手工在 notify.yaml 里直接填写的明文（如 webhook_url），
        此时 value 本身就不是密文，解密抛异常属预期行为，不做告警以免刷屏。
        """
        if not value:
            return ""
        try:
            return CryptoUtils.decrypt(value, self.key)
        except Exception:  # noqa: BLE001
            return value

    def _encrypt(self, value):
        if not value:
            return ""
        return CryptoUtils.encrypt(value, self.key)

    # ---------------- 渠道状态 ----------------
    def get_channels_status(self):
        """返回各渠道状态列表"""
        result = []
        for cid, name in CHANNEL_NAMES.items():
            cfg = self.config.get(cid, {}) or {}
            enabled = bool(cfg.get("enabled"))
            status = "active" if enabled else "disabled"
            result.append({
                "id": cid,
                "name": name,
                "enabled": enabled,
                "status": status,
                "template": cfg.get("template", "default"),
                "priority": cfg.get("priority", "normal"),
            })
        return result

    # ---------------- 模板渲染 ----------------
    def render(self, template_id, ctx):
        """使用指定模板（或 default）渲染消息"""
        templates = self.config.get("templates", {}) or {}
        tpl = templates.get(template_id) or templates.get("default", "")
        return GoTemplate(tpl).render(ctx)

    # ---------------- 频率限制 ----------------
    def _rate_limited(self, channel):
        rate = _get_rate_limit_config()
        if not rate.get("enabled", True):
            return False
        min_interval = int(rate.get("min_interval_seconds", 60))
        with self._lock:
            last = self._last_send.get(channel)
            if last and (datetime.now(timezone.utc).timestamp() - last) < min_interval:
                return True
        return False

    def _mark_sent(self, channel):
        with self._lock:
            self._last_send[channel] = datetime.now(timezone.utc).timestamp()

    # ---------------- 发送 ----------------
    def send(self, channels, title, content, priority="normal", recipients=None,
             template_id=None, source="system", extra=None):
        """
        统一发送通知。
        返回 [{"channel", "success", "message"}, ...]
        """
        results = []
        for channel in channels:
            cfg = self.config.get(channel, {}) or {}
            if not cfg.get("enabled"):
                results.append({"channel": channel, "success": False, "message": "渠道未启用"})
                continue
            if self._rate_limited(channel):
                msg = "频率限制，请 %d 秒后再试" % int(
                    _get_rate_limit_config().get("min_interval_seconds", 60)
                )
                audit_log("notify_send", "渠道:%s 频率限制" % channel, "failed", username="system")
                results.append({"channel": channel, "success": False, "message": msg})
                continue
            ctx = {
                "Title": title,
                "Content": content,
                "Priority": priority,
                "Channel": channel,
                "Time": datetime.now(timezone.utc).isoformat(),
                "Source": source,
                "Extra": extra or {},
            }
            tpl_id = template_id or cfg.get("template", "default")
            rendered = self.render(tpl_id, ctx)
            ok, message = self._dispatch(channel, cfg, rendered, recipients)
            # 无论成功失败都记时间戳：发送失败往往是对端限流/网络故障，
            # 立刻重试只会加剧问题，因此失败同样受最小间隔约束
            self._mark_sent(channel)
            audit_log(
                "notify_send",
                "渠道:%s, 标题:%s, 收件人:%s" % (channel, title, recipients or "默认"),
                "success" if ok else "failed",
                username="system",
            )
            if not ok:
                logger.warning("通知发送失败（%s）：%s", channel, message)
            results.append({"channel": channel, "success": ok, "message": message})
        return results

    def _dispatch(self, channel, cfg, rendered, recipients):
        """根据渠道分发到具体发送实现"""
        try:
            if channel == "email":
                return self._send_email(cfg, rendered, recipients)
            if channel == "wechat_work":
                return self._send_webhook(self._decrypt(cfg.get("webhook_url")), rendered, "markdown")
            if channel == "dingtalk":
                return self._send_dingtalk(cfg, rendered)
            if channel == "feishu":
                return self._send_webhook(self._decrypt(cfg.get("webhook_url")), rendered, "text")
        except Exception as exc:  # noqa: BLE001
            return False, "发送异常：%s" % exc
        return False, "未知渠道"

    def _send_email(self, cfg, rendered, recipients):
        host = cfg.get("smtp_host")
        if not host:
            return False, "未配置 SMTP 服务器"
        port = int(cfg.get("smtp_port", 465))
        use_ssl = bool(cfg.get("smtp_ssl", True))
        user = cfg.get("username")
        pwd = self._decrypt(cfg.get("password"))
        sender = cfg.get("sender_name", "NetCore Framework")
        to_list = recipients or cfg.get("default_recipients", []) or []
        if isinstance(to_list, str):
            to_list = [x.strip() for x in to_list.split(",") if x.strip()]
        if not to_list:
            return False, "未指定收件人"
        msg = MIMEText(rendered, "plain", "utf-8")
        msg["Subject"] = "NetCore Framework 通知"
        msg["From"] = "%s <%s>" % (sender, user) if user else sender
        msg["To"] = ", ".join(to_list)
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                    if user and pwd:
                        server.login(user, pwd)
                    server.sendmail(user or sender, to_list, msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.starttls()
                    if user and pwd:
                        server.login(user, pwd)
                    server.sendmail(user or sender, to_list, msg.as_string())
            return True, "已发送"
        except Exception as exc:  # noqa: BLE001
            return False, "邮件发送失败：%s" % exc

    def _send_webhook(self, url, rendered, msgtype):
        if not url:
            return False, "未配置 Webhook 地址"
        payload = {"msgtype": "text", "text": {"content": rendered}}
        if msgtype == "markdown":
            payload = {"msgtype": "markdown", "markdown": {"content": rendered}}
        resp = httpx.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, "已发送"
        return False, "HTTP %d: %s" % (resp.status_code, resp.text[:200])

    def _send_dingtalk(self, cfg, rendered):
        url = self._decrypt(cfg.get("webhook_url"))
        if not url:
            return False, "未配置 Webhook 地址"
        secret = self._decrypt(cfg.get("secret"))
        # 钉钉加签：待签字符串固定为 "毫秒时间戳\n加签密钥"，
        # 以密钥为 key 做 HMAC-SHA256 后 Base64。
        if secret:
            timestamp = str(round(datetime.now(timezone.utc).timestamp() * 1000))
            string_to_sign = "%s\n%s" % (timestamp, secret)
            hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            # Base64 结果可能含 +、/、= 等字符，直接拼进 query 会被服务端解析错
            # （+ 会被当成空格），导致「sign not match」，必须先做 URL 编码
            sign = urllib.parse.quote_plus(sign)
            sep = "&" if "?" in url else "?"
            url = "%s%ssign=%s&timestamp=%s" % (url, sep, sign, timestamp)
        payload = {"msgtype": "text", "text": {"content": rendered}}
        resp = httpx.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, "已发送"
        return False, "HTTP %d: %s" % (resp.status_code, resp.text[:200])

    # ---------------- 测试渠道 ----------------
    def test_channel(self, channel, recipients=None):
        """测试指定渠道是否可用"""
        cfg = self.config.get(channel, {}) or {}
        if not cfg.get("enabled"):
            return False, "渠道未启用"
        ctx = {
            "Title": "测试通知",
            "Content": "这是一条来自 NetCore Framework 的测试消息。",
            "Priority": "normal",
            "Channel": channel,
            "Time": datetime.now(timezone.utc).isoformat(),
            "Source": "system",
            "Extra": {},
        }
        rendered = self.render(cfg.get("template", "default"), ctx)
        ok, message = self._dispatch(channel, cfg, rendered, recipients)
        audit_log("notify_test", "渠道:%s" % channel, "success" if ok else "failed", username="system")
        return ok, message

    # ---------------- 配置读取（脱敏）与保存 ----------------
    def get_config_masked(self):
        """返回通知配置，敏感字段脱敏为 ********"""
        out = {}
        for cid, cfg in self.config.items():
            if cid == "templates":
                out[cid] = cfg
                continue
            item = dict(cfg) if isinstance(cfg, dict) else cfg
            for field in SENSITIVE_FIELDS.get(cid, []):
                if item.get(field):
                    item[field] = MASK
            out[cid] = item
        return out

    def save_config(self, raw):
        """
        保存通知配置。
        规则：若某敏感字段传入空字符串或掩码 ********，则保留原加密值不更新；
              否则对明文敏感字段加密后写入。
        """
        current = get_notify_config()
        for cid, fields in SENSITIVE_FIELDS.items():
            if cid not in raw:
                continue
            incoming = raw[cid]
            existing = current.get(cid, {}) or {}
            for field in fields:
                val = incoming.get(field)
                if val in (None, "", MASK):
                    # 不更新，保留原值（可能为加密字符串或空）
                    incoming[field] = existing.get(field, "")
                else:
                    incoming[field] = self._encrypt(val)
        # templates 直接覆盖
        if "templates" in raw:
            current["templates"] = raw["templates"]
        for cid, value in raw.items():
            if cid == "templates":
                continue
            current[cid] = value
        save_notify_config(current)
        self.reload()
        audit_log("notify_config_changed", "通知配置已更新", "success", username="system")
        return True


_notify_manager = NotifyManager()


def get_notify_manager() -> NotifyManager:
    return _notify_manager
