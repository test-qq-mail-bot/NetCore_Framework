"""
config_loader.py - 全局配置加载模块

功能：读取 YAML 配置文件，校验配置项合法性
若配置文件不存在则自动生成默认配置
程序首次运行时会自动创建所需目录结构
"""
import base64
import hashlib
import hmac
import os
import sys
import threading
from pathlib import Path

import yaml

from core.crypto_utils import CryptoUtils


# ------------------------------------------------------------------
# 原子写入 + 并发保护（审查报告 #4 修复）
# ------------------------------------------------------------------
_cfg_locks = {
    "user": threading.RLock(),
    "security": threading.RLock(),
    "notify": threading.RLock(),
}


def _atomic_write_text(path: Path, text: str):
    """原子写入文本文件：先写临时文件再 os.replace，避免断电/崩溃留下半截文件。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)      # 同盘原子操作


def _restrict_file_perms(path: Path):
    """收紧敏感文件权限（审查报告 #5）。

    POSIX: chmod 0o600（仅文件属主可读写）；
    Windows: best-effort 用 icacls 收紧到当前用户（失败仅告警不影响启动）。
    """
    try:
        if os.name == "posix":
            os.chmod(path, 0o600)
        elif os.name == "nt":
            import subprocess
            username = os.environ.get("USERNAME", "")
            if username:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", "%s:F" % username],
                    capture_output=True, timeout=5,
                )
    except Exception as exc:
        try:
            from core.logger import get_logger
            get_logger().warning("收紧文件权限失败（%s）：%s", path, exc)
        except Exception:  # noqa: BLE001
            pass

# ------------------------------------------------------------------
# 程序根目录（配置文件与数据文件均存放于此）
# 打包后 sys.executable 为 exe 路径；开发模式下为项目根目录
# ------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # 原实现把 os.getcwd 作为候选优先，导致从不同工作目录启动 EXE 时 BASE_DIR 漂移，
    # plugins/ 与 SQLite 数据库落到不同路径，设备数据重启即丢失。
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
AUDIT_DIR = LOG_DIR / "audit"
PLUGINS_DIR = BASE_DIR / "plugins"
FRONTEND_DIR = BASE_DIR / "frontend"
WIKI_DIR = BASE_DIR / "wiki"

# 系统名称与版本硬编码默认值（可被 user_config.yaml 覆盖）
SYSTEM_NAME = "NetCore Framework"
# 插件前端清单按文件 mtime 自动追加 ?v= 版本参数（插件 JS 改动即失效浏览器缓存，
# 不再依赖手工同步的全局版本号）
# core.yaml 恢复中文注释（文本级迁移，logging/session/https/debug 迁 user_config
# 且不留「迁移自」标注）、log-level 落盘、审计记录配置修改前后差异、EXE 版本资源、
SYSTEM_VERSION = "20260827-V3"

# 全局配置缓存
_config_cache = {}
# 配置缓存读写锁：避免多线程并发读写 _config_cache 出现半更新/互相覆盖
_config_cache_lock = threading.Lock()


# ------------------------------------------------------------------
# 默认配置文件内容（含中文注释，首次启动时写入磁盘）
# 审查清理：移除无引用的 DEFAULT_USER_CONFIG 字符串常量——user_config.yaml
# 实际由 _write_default_configs 中的字典 + _render_user_config_commented 生成，
# 模板字符串是历史遗留死代码，且与真实渲染产物不同步，易误导维护者。
# ------------------------------------------------------------------

DEFAULT_SECURITY_CONFIG = """\
# ============================================================
# 安全策略配置文件（可读写）
# 修改后立即生效，无需重启服务
# ============================================================

failure_policy:
  max_failures: 5         # 连续失败达到此次数后封禁
  block_minutes: 10       # 封禁时长（分钟）
  reset_interval_minutes: 30  # 失败计数重置间隔（分钟）

whitelist:                # IP 白名单：受信任来源 IP（如管理员办公 IP），仅作「免锁定放行」用途，并非防火墙。
                          # 命中白名单的 IP 直接放行且不受登录失败锁定策略约束；不会因此限制其他正常用户访问。
                          # 条目可带说明与有效期：{ip: "x.x.x.x", note: "管理员办公IP", expires_at: "2026-12-31T23:59:59"}
  # 以下回环条目仅在本文件首次创建时写入；此后框架不再自动增删，可按需移除
  - ip: "127.0.0.1"
    note: "系统初始化-本地管理通道"
    expires_at: null
  - ip: "::1"
    note: "系统初始化-本地管理通道"
    expires_at: null
  # - ip: "192.168.1.100"
  #   note: "管理员办公IP"
  #   expires_at: "2026-12-31T23:59:59"
  # - "10.0.0.0/8"

blacklist: []             # IP 黑名单（自动封禁或手动添加）；命中且在封禁期内返回 404 以隐藏存在
  # - ip: "203.0.113.45"
  #   block_until: "2026-07-07T10:30:00Z"
  #   reason: "连续5次失败"
  #   note: "可疑扫描"
  #   fail_count: 5
"""

DEFAULT_NOTIFY_CONFIG = """\
# ============================================================
# 通知管理配置（可读写）
# 作用：配置系统的各类通知渠道（邮件 / 企业微信 / 钉钉 / 飞书），
#       用于向管理员推送设备告警、配置备份失败、任务完成等消息。
# 说明：
#   1. 密码、Webhook URL 等敏感字段使用 AES-256-GCM 加密存储，
#      手工填写明文会在首次读取时自动加密落盘；
#   2. 修改本文件后**立即生效**（无需重启程序），也可通过
#      「系统设置-通知管理」Web 后台进行可视化配置；
#   3. 渠道 enabled 为 false 时不发送任何消息（默认全部关闭）。
# ============================================================

# ---------- 全局消息模板 ----------
# 可被各渠道引用（Go template 语法），支持以下变量：
#   {{.Title}}    消息标题（如"设备告警：核心交换机A"）
#   {{.Content}}  消息正文内容
#   {{.Priority}} 优先级（high / normal / low）
#   {{.Time}}     触发时间
#   {{.Source}}   消息来源（如"数通配置卫士"）
# 渠道配置里的 template 字段填哪个模板 id，就用哪个模板渲染消息。
templates:
  # default：通用模板——高优先级消息自动加[紧急]前缀
  default: |
    {{if eq .Priority "high"}}[紧急] {{end}}{{.Title}}
    时间：{{.Time}}
    来源：{{.Source}}
    {{.Content}}
  # alert：告警模板——适合设备告警类消息，以醒目格式展示
  alert: |
    **告警通知**
    > 标题：{{.Title}}
    > 优先级：{{.Priority}}
    > 时间：{{.Time}}
    > 来源：{{.Source}}
    {{.Content}}
  # info：信息模板——普通通知消息
  info: |
    信息通知：{{.Title}}
    {{.Content}}

# ---------- 邮件渠道（SMTP） ----------
# 适用场景：发送备份报告、周期性汇总邮件。
# 需要你有可用的 SMTP 服务器（如企业邮箱、QQ 邮箱、163 邮箱）。
email:
  enabled: false                    # 是否启用邮件渠道（true=启用 / false=停用）
  smtp_host: ""                     # SMTP 服务器地址（如 smtp.qq.com、smtp.163.com）
  smtp_port: 465                    # SMTP 端口：465=SSL 加密 / 587=STARTTLS（选其一）
  smtp_ssl: true                    # 是否使用 SSL 加密（true=465端口SSL / false=587端口STARTTLS）
  username: ""                      # 发件人邮箱账号（如 admin@example.com）
  password: ""                      # 发件人邮箱密码 / 授权码（敏感字段，加密存储）
  sender_name: "NetCore Framework"  # 发件人显示名称（收件人看到的发件人名字）
  default_recipients: []            # 默认收件人列表，如 ["a@example.com", "b@example.com"]
  cc: []                            # 默认抄送人列表（可选，留空表示不抄送）
  bcc: []                           # 默认密送人列表（可选，留空表示不密送）
  priority: "normal"                # 该渠道消息优先级：high / normal / low
  template: "default"               # 使用的消息模板 id（见上方 templates）

# ---------- 企业微信渠道 ----------
# 适用场景：通过企业微信群机器人推送告警，手机端实时收到。
# 配置方法：在企业微信群 → 添加群机器人 → 复制 Webhook 地址填入下方。
wechat_work:
  enabled: false                    # 是否启用企业微信渠道（true=启用 / false=停用）
  webhook_url: ""                   # 群机器人 Webhook 地址（敏感字段，加密存储）
  priority: "normal"                # 该渠道消息优先级：high / normal / low
  template: "default"               # 使用的消息模板 id（见上方 templates）

# ---------- 钉钉渠道 ----------
# 适用场景：通过钉钉群机器人推送告警，手机端实时收到。
# 配置方法：钉钉群 → 群设置 → 智能群助手 → 添加自定义机器人（选择"加签"方式），
#           将 Webhook 地址与加签密钥填入下方。
dingtalk:
  enabled: false                    # 是否启用钉钉渠道（true=启用 / false=停用）
  webhook_url: ""                   # 自定义机器人 Webhook 地址（敏感字段，加密存储）
  secret: ""                        # 加签密钥（安全设置选"加签"时必填；敏感字段，加密存储）
  priority: "normal"                # 该渠道消息优先级：high / normal / low
  template: "default"               # 使用的消息模板 id（见上方 templates）

# ---------- 飞书渠道 ----------
# 适用场景：通过飞书群机器人推送告警，手机端实时收到。
# 配置方法：飞书群 → 设置 → 群机器人 → 添加自定义机器人（选择"签名校验"方式），
#           将 Webhook 地址与签名密钥填入下方。
feishu:
  enabled: false                    # 是否启用飞书渠道（true=启用 / false=停用）
  webhook_url: ""                   # 自定义机器人 Webhook 地址（敏感字段，加密存储）
  secret: ""                        # 签名校验密钥（安全设置选"签名校验"时必填；敏感字段，加密存储）
  priority: "normal"                # 该渠道消息优先级：high / normal / low
  template: "default"               # 使用的消息模板 id（见上方 templates）
"""


def _default_core_yaml(enc_key: str, jwt_secret: str) -> str:
    """生成核心配置 YAML 文本。

    加密密钥与 JWT 密钥**只在 core.yaml 不存在时生成一次**并写入磁盘长期沿用
    （见 _write_default_configs），不是每次启动都重新生成。
    """
    return """\
# ============================================================
# NetCore Framework 核心配置文件
# 此文件只读，修改需重启服务生效
# 若文件不存在，框架启动时自动生成
# ============================================================

# ---------- 服务配置 ----------
server:
  host: "0.0.0.0"          # 监听地址，0.0.0.0 表示监听所有网卡
  port: 8080               # 监听端口号
# 说明：调试模式（debug）与 HTTPS 等可调配置项已统一移至 user_config.yaml，
# core.yaml 只保留 host/port 等启动必备的只读参数，保持核心配置最小化。

# ---------- 加密密钥 ----------
crypto:
  encryption_key: "%s"     # AES-256-GCM 加密密钥（Base64编码），首次启动自动生成

# ---------- JWT 认证配置 ----------
jwt:
  secret_key: "%s"         # JWT 签名密钥：仅在首次生成本文件时随机产生并固定保存。
                           # 必须保持稳定，否则重启/多进程后已签发的 token 会校验失败（随机 401）。
                           # 若此项为空，框架回退使用 data/.secret_key（自动生成并持久化）。
                           # 更换该值等同于强制所有用户重新登录。
  expire_minutes: 1440     # Token 有效期（分钟），默认 24 小时
""" % (enc_key, jwt_secret)


# ------------------------------------------------------------------
# 目录与权限
# ------------------------------------------------------------------
def _ensure_write_permission():
    """检查程序根目录是否可写，不可写则直接报错退出"""
    # 优先使用 os.access 判断写权限（不触发任何删除操作，兼容安全删除环境）
    if not os.access(BASE_DIR, os.W_OK):
        raise SystemExit(
            "[致命] 程序目录无写入权限，无法运行：%s" % BASE_DIR
        )
    # 额外验证：尝试创建一个临时探测文件
    test_file = BASE_DIR / ".write_test"
    try:
        test_file.write_text("")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "[致命] 程序目录无写入权限，无法运行：%s\n错误：%s" % (BASE_DIR, exc)
        )
    # 尝试删除探测文件；若删除被环境拦截（如安全删除机制），属正常现象，忽略
    try:
        test_file.unlink()
    except Exception:  # noqa: BLE001
        pass


def ensure_directories():
    """创建运行所需目录结构（首次运行）"""
    _ensure_write_permission()
    for directory in (CONFIG_DIR, DATA_DIR, LOG_DIR, AUDIT_DIR, PLUGINS_DIR, FRONTEND_DIR, WIKI_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# 默认配置生成
# ------------------------------------------------------------------
def _discover_plugin_names() -> list:
    """扫描 plugins/ 目录，返回包含 plugin.py 的插件名列表（不依赖 plugin_manager，避免循环导入）"""
    names = []
    if PLUGINS_DIR.exists():
        for sub in sorted(PLUGINS_DIR.iterdir()):
            if sub.is_dir() and (sub / "plugin.py").exists():
                names.append(sub.name)
    return names


def _write_default_configs():
    """若配置文件不存在则生成默认文件"""
    if not (CONFIG_DIR / "core.yaml").exists():
        enc_key = CryptoUtils.generate_key()
        jwt_secret = CryptoUtils.generate_key()
        _atomic_write_text(CONFIG_DIR / "core.yaml", _default_core_yaml(enc_key, jwt_secret))
        _restrict_file_perms(CONFIG_DIR / "core.yaml")
    if not (CONFIG_DIR / "user_config.yaml").exists():
        # 直接构造完整配置字典并用带注释的渲染器写出，彻底避免「模板字符串替换」因
        # 缩进/空格/正则匹配失败导致默认密码哈希或 detected 未写入的历史隐患。
        default_hash = CryptoUtils.hash_password("Admin@123!")
        # 首次启动：扫描 plugins/ 目录，将所有检测到的插件写入 detected 列表
        # （之后每次启动由 refresh_detected_plugins 维护；disabled 默认空=启用全部）
        discovered = _discover_plugin_names()
        default_user_cfg = {
            "system": {
                "name": "",
                "version": "",
                "auto_logout_minutes": 5,
                "timezone": "Asia/Shanghai",
                "auto_update_timezone": True,
            },
            "auth": {
                "username": "admin",
                "password_hash": default_hash,
                "totp_enabled": False,
                "totp_secret": "",
                "last_login_time": "",
                "last_login_ip": "",
            },
            "plugins": {
                "detected": discovered,
                "disabled": [],
            },
            "logging": {
                "level": "INFO",
                "file": "data/logs/",
                "max_bytes": 10485760,
                "backup_count": 30,
                "audit_log_retention_days": 60,
            },
            "notify": {
                "rate_limit": {
                    "enabled": True,
                    "min_interval_seconds": 60,
                }
            },
            # HTTPS 证书/私钥以 PEM 文本存储（cert_content/key_content），
            # 不再存文件路径（路径易随文件丢失而失效）；server.debug 与 session.idle_timeout_minutes
            # 已删除——日志等级统一由 logging.level、自动退出统一由 system.auto_logout_minutes 控制
            "https": {
                "enabled": True,
                "cert_content": "",
                "key_content": "",
                "auto_redirect": True,
                "redirect_port": "",
                "domain": "",
            },
            # 审查报告 #2/#3：安全相关开关
            "security": {
                "enable_docs": False,           # Swagger 文档默认关闭，调试时改 true
                "trusted_proxies": ["127.0.0.1", "::1"],  # 反向代理可信对端 IP，仅这些 IP 的 X-Forwarded-For 会被信任
            },
        }
        _atomic_write_text(CONFIG_DIR / "user_config.yaml", _render_user_config_commented(default_user_cfg))
        _restrict_file_perms(CONFIG_DIR / "user_config.yaml")
    if not (CONFIG_DIR / "security.yaml").exists():
        (CONFIG_DIR / "security.yaml").write_text(DEFAULT_SECURITY_CONFIG, encoding="utf-8")
    if not (CONFIG_DIR / "notify.yaml").exists():
        (CONFIG_DIR / "notify.yaml").write_text(DEFAULT_NOTIFY_CONFIG, encoding="utf-8")


def _recomment_existing_configs():
    """若已生成的配置文件被 safe_dump 覆盖而丢失中文注释，则按当前值重写带注释版本。
    已带注释（以 # 开头）的文件保持不变，保证幂等且不破坏用户手写注释。

    notify.yaml 纳入重写——用户环境里该文件仅保留旧版简单注释，
    保存一次后注释即丢失；此处检测「首行无注释」或「缺少详细中文注释标识」时，
    按当前值重写为详细中文注释版本。
    """
    for fname, render in (
        ("user_config.yaml", _render_user_config_commented),
        ("security.yaml", _render_security_config_commented),
        ("notify.yaml", _render_notify_config_commented),
    ):
        p = CONFIG_DIR / fname
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        if text.lstrip().startswith("#"):
            # 已带注释：notify.yaml 额外检查是否已是「详细中文注释」版本（V2 标识）
            if fname != "notify.yaml" or "邮件渠道（SMTP）" in text:
                continue
        try:
            from core.logger import get_logger
            data = _read_yaml(p) or {}
            p.write_text(render(data), encoding="utf-8")
            get_logger().info("已为 %s 补回中文注释", fname)
        except Exception as exc:  # noqa: BLE001
            try:
                from core.logger import get_logger
                get_logger().warning("重写带注释配置 %s 失败：%s", fname, exc)
            except Exception:
                pass


def _ensure_password_hash():
    """兜底修复：若 user_config.yaml 的 password_hash 为空或缺失（例如旧版/损坏配置、
    或前次构建未正确写入默认哈希），则用默认密码 Admin@123! 重新生成哈希写回，
    避免管理员被永久锁死无法登录。

    - 仅在哈希为空/缺失时触发，已有有效哈希则保持不动（不覆盖用户已修改的密码）。
    - 复用带注释渲染器，保留用户的其他配置与中文注释。
    """
    p = CONFIG_DIR / "user_config.yaml"
    if not p.exists():
        return
    try:
        data = _read_yaml(p) or {}
    except Exception:  # noqa: BLE001
        return
    auth = data.get("auth") or {}
    existing = auth.get("password_hash") if isinstance(auth, dict) else None
    if existing:
        return  # 已有有效哈希，无需处理
    default_hash = CryptoUtils.hash_password("Admin@123!")
    if not isinstance(data.get("auth"), dict):
        data["auth"] = {}
    data["auth"]["password_hash"] = default_hash
    data["auth"].setdefault("username", "admin")
    try:
        p.write_text(_render_user_config_commented(data), encoding="utf-8")
        try:
            from core.logger import get_logger
            get_logger().warning(
                "user_config.yaml 的 password_hash 为空，已用默认密码 Admin@123! 重建哈希"
            )
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        try:
            from core.logger import get_logger
            get_logger().error("重建 password_hash 失败：%s", exc)
        except Exception:  # noqa: BLE001
            pass


def _ensure_user_config_defaults():
    """自动补齐 user_config.yaml 缺失的默认键。

    - system.timezone / system.auto_update_timezone：旧实例无时区参数时补齐；
    - logging / notify / https：旧实例迁移后补齐。
    - 删除已废弃的 session 段与 server.debug（日志等级由 logging.level
      统一控制、自动退出由 system.auto_logout_minutes 统一控制）；旧版 https.cert_file/
      key_file 文件路径自动读取内容转存为 PEM 文本（cert_content/key_content）。
    仅当存在缺失键/废弃段时才写盘（带注释渲染，保留用户已有配置），避免无谓 IO。
    """
    p = CONFIG_DIR / "user_config.yaml"
    if not p.exists():
        return
    try:
        cfg = _read_yaml(p) or {}
    except Exception:  # noqa: BLE001
        return
    changed = False
    if not isinstance(cfg.get("system"), dict):
        cfg["system"] = {}
    if "timezone" not in cfg["system"]:
        cfg["system"]["timezone"] = "Asia/Shanghai"
        changed = True
    if "auto_update_timezone" not in cfg["system"]:
        cfg["system"]["auto_update_timezone"] = True
        changed = True
    if "default_page_size" not in cfg["system"]:
        cfg["system"]["default_page_size"] = 10
        changed = True
    if not isinstance(cfg.get("logging"), dict):
        cfg["logging"] = {
            "level": "INFO",
            "file": "data/logs/",
            "max_bytes": 10485760,
            "backup_count": 30,
            "audit_log_retention_days": 60,
        }
        changed = True
    if not isinstance(cfg.get("notify"), dict):
        cfg["notify"] = {"rate_limit": {"enabled": True, "min_interval_seconds": 60}}
        changed = True
    elif not isinstance(cfg["notify"].get("rate_limit"), dict):
        cfg["notify"]["rate_limit"] = {"enabled": True, "min_interval_seconds": 60}
        changed = True
    if "session" in cfg:
        cfg.pop("session", None)
        changed = True
    if "server" in cfg:
        cfg.pop("server", None)
        changed = True
    if not isinstance(cfg.get("https"), dict):
        cfg["https"] = {"enabled": True, "cert_content": "", "key_content": "", "domain": ""}
        changed = True
    else:
        _h = cfg["https"]
        if _h.get("cert_file") or _h.get("key_file"):
            for _f, _k in (("cert_file", "cert_content"), ("key_file", "key_content")):
                if _h.get(_k):
                    _h.pop(_f, None)
                    continue
                try:
                    _p = Path(str(_h.get(_f) or ""))
                    _h[_k] = _p.read_text(encoding="utf-8") if _p.is_file() else ""
                except Exception:  # noqa: BLE001
                    _h[_k] = ""
                _h.pop(_f, None)
            changed = True
        if not _h.get("cert_content"):
            _h["cert_content"] = ""
        if not _h.get("key_content"):
            _h["key_content"] = ""
        if "cert_file" in _h or "key_file" in _h:
            _h.pop("cert_file", None)
            _h.pop("key_file", None)
            changed = True
        if "auto_redirect" not in _h:
            _h["auto_redirect"] = True
            changed = True
        if "redirect_port" not in _h:
            _h["redirect_port"] = ""
            changed = True
        if "domain" not in _h:
            _h["domain"] = ""
            changed = True
    # 审查报告 #2/#3：补齐 security 段（enable_docs / trusted_proxies）
    if not isinstance(cfg.get("security"), dict):
        cfg["security"] = {}
        changed = True
    _sec = cfg["security"]
    if "enable_docs" not in _sec:
        _sec["enable_docs"] = False
        changed = True
    if "trusted_proxies" not in _sec:
        _sec["trusted_proxies"] = ["127.0.0.1", "::1"]
        changed = True
    if not changed:
        return
    try:
        _atomic_write_text(p, _render_user_config_commented(cfg))
        try:
            from core.logger import get_logger
            get_logger().info("user_config.yaml 已自动补齐/清理默认键（timezone/logging/notify/https；已移除 session/server.debug）")
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        try:
            from core.logger import get_logger
            get_logger().warning("自动补齐 user_config.yaml 默认键失败：%s", exc)
        except Exception:  # noqa: BLE001
            pass


def _strip_yaml_sections(text: str, sections: set) -> str:
    """按「顶级键」文本级删除 YAML 段，保留其余段落与中文注释。

    - 从段名行（无缩进的 key:）开始，连同其后的缩进行/空行/紧邻注释一起删除，
      直到下一个非空、非缩进、非注释的行（下一个顶级键）为止；
    - 段前的注释头（# ---------- xxx ----------）一并删除；
    - 不影响其他段落与注释（区别于 yaml.safe_dump 重写会抹掉全部注释）。
    """
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if line[:1] not in ("", " ", "\t", "#") and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key in sections:
                # 回退删除该段前的注释头行（# 开头且连续）
                while out and out[-1].strip().startswith("#"):
                    out.pop()
                i += 1
                # 吞掉段内：空行 / 缩进行 / 注释行，直到下一个非空非缩进非注释行
                while i < len(lines):
                    cur = lines[i]
                    if not cur.strip() or cur[:1] in (" ", "\t", "#"):
                        i += 1
                        continue
                    break
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _migrate_legacy_core_sections():
    """将旧 core.yaml 中遗留的可调配置段整体迁移至 user_config.yaml，
    并从 core.yaml **文本级删除**（保留其余段与中文注释）。

    迁移段：logging / notify。
    - 值合并：以 user_config.yaml 已有值为准，缺失键才用 core.yaml 旧值补齐；
    - core.yaml 删除采用文本级段落裁剪（_strip_yaml_sections），不再 safe_dump 重写，
      彻底解决「迁移后中文注释丢失」问题；
    - session/https 段与 server.debug 不再迁移（session 由
      system.auto_logout_minutes、日志等级由 logging.level 统一控制；https 证书
      改为 PEM 文本存储），core.yaml 中残留的上述段一并文本级删除（server 段保留
      host/port，仅移除 debug 行）。
    """
    core_p = CONFIG_DIR / "core.yaml"
    user_p = CONFIG_DIR / "user_config.yaml"
    if not core_p.exists() or not user_p.exists():
        return
    try:
        core = _read_yaml(core_p) or {}
        core_text = core_p.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return
    try:
        user = _read_yaml(user_p) or {}
    except Exception:  # noqa: BLE001
        user = {}
    sections_in_core = [s for s in ("logging", "notify") if s in core]
    changed_user = False
    for section in ("logging", "notify"):
        if section not in core:
            continue
        core_sec = core.get(section) or {}
        user_sec = user.get(section) or {}
        merged = dict(core_sec)
        merged.update({k: v for k, v in (user_sec or {}).items() if v is not None})
        if merged != user_sec:
            user[section] = merged
            changed_user = True
    if changed_user:
        try:
            user_p.write_text(_render_user_config_commented(user), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            try:
                from core.logger import get_logger
                get_logger().warning("迁移配置段至 user_config.yaml 失败：%s", exc)
            except Exception:  # noqa: BLE001
                pass
    # core.yaml 文本级删除迁移段（保留注释）；server.debug 单独从 server 段删掉该行
    remove_top = {"logging", "notify", "session", "https"}
    server_has_debug = isinstance(core.get("server"), dict) and "debug" in core.get("server", {})
    need_strip = bool(remove_top & set(core.keys())) or server_has_debug
    if need_strip:
        new_text = _strip_yaml_sections(core_text, remove_top)
        if server_has_debug:
            # 删除 server 段内的 debug 行（保留 host/port 及注释）
            kept = []
            for ln in new_text.split("\n"):
                if ln.strip().startswith("debug:"):
                    continue
                kept.append(ln)
            new_text = "\n".join(kept)
        if new_text.strip() != core_text.strip():
            try:
                core_p.write_text(new_text, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                try:
                    from core.logger import get_logger
                    get_logger().warning("清理 core.yaml 遗留配置段失败：%s", exc)
                except Exception:  # noqa: BLE001
                    pass


def refresh_detected_plugins():
    """每次启动时扫描 plugins/ 目录，将当前存在的插件同步到 user_config.yaml 的 plugins.detected。

    - detected 仅作记录，不参与启停判定；启停由 disabled 列表控制。
    - 不改动 disabled（管理员显式选择），仅让 detected 随时反映磁盘上的实际插件。
    - 仅当 detected 实际变化时才写盘，避免无谓 IO。
    - 直接读取磁盘上的 user_config.yaml（而非带缓存的 get_user_config），避免读到
      bootstrap 早期因文件尚未生成而缓存的空配置，从而错误覆盖 auth/password_hash 等字段。
    """
    discovered = sorted(_discover_plugin_names())
    try:
        cfg = _read_yaml(CONFIG_DIR / "user_config.yaml") or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    if not isinstance(cfg.get("plugins"), dict):
        cfg["plugins"] = {}
    current = sorted(cfg["plugins"].get("detected") or [])
    if current == discovered:
        return  # 无变化，避免无谓写盘
    cfg["plugins"]["detected"] = discovered
    try:
        save_user_config(cfg)
    except Exception as exc:  # noqa: BLE001
        try:
            from core.logger import get_logger
            get_logger().warning("刷新 detected 插件列表失败：%s", exc)
        except Exception:
            pass


def bootstrap():
    """程序启动时引导配置：创建目录并生成默认配置"""
    ensure_directories()
    _write_default_configs()
    _ensure_password_hash()      # 兜底：修复空/缺失的默认密码哈希，避免锁死
    refresh_detected_plugins()   # 每次启动重新扫描插件目录，更新 detected 列表
    _migrate_legacy_core_sections()  # 旧 core.yaml 遗留 logging/notify/session/https/debug 迁移（保留注释）
    _ensure_user_config_defaults()  # 自动补齐缺失默认键（timezone/logging/notify/session/https/debug）
    _recomment_existing_configs()
    _config_cache.clear()


# ------------------------------------------------------------------
# 配置读写
# ------------------------------------------------------------------
def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _yaml_scalar_str(v) -> str:
    """将 python 标量格式化为 YAML 行内值（字符串统一加双引号，bool/None 按字面量）"""
    if v is None:
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return ('"' + str(v).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r", "\\r").replace("\n", "\\n") + '"')


def _render_user_config_commented(cfg: dict) -> str:
    """带中文注释地重新渲染 user_config.yaml，保留当前值（避免 safe_dump 抹除注释）"""
    system = cfg.get("system", {}) or {}
    auth = cfg.get("auth", {}) or {}
    plugins = cfg.get("plugins", {}) or {}
    disabled = plugins.get("disabled") or []
    detected = plugins.get("detected") or []
    name = _yaml_scalar_str(system.get("name", ""))
    version = _yaml_scalar_str(system.get("version", ""))
    auto_logout = int(system.get("auto_logout_minutes", 5) or 5)
    timezone = _yaml_scalar_str(system.get("timezone", "Asia/Shanghai"))
    auto_update_timezone = _yaml_scalar_str(bool(system.get("auto_update_timezone", True)))
    default_page_size = int(system.get("default_page_size", 10) or 10)
    logging_cfg = cfg.get("logging", {}) or {}
    notify_cfg = cfg.get("notify", {}) or {}
    https_cfg = cfg.get("https", {}) or {}
    log_level = _yaml_scalar_str(logging_cfg.get("level", "INFO"))
    log_file = _yaml_scalar_str(logging_cfg.get("file", "data/logs/"))
    log_max_bytes = int(logging_cfg.get("max_bytes", 10485760) or 10485760)
    log_backup = int(logging_cfg.get("backup_count", 30) or 30)
    log_retention = int(logging_cfg.get("audit_log_retention_days", 60) or 60)
    rate_limit = notify_cfg.get("rate_limit", {}) or {}
    notify_enabled = _yaml_scalar_str(bool(rate_limit.get("enabled", True)))
    notify_interval = int(rate_limit.get("min_interval_seconds", 60) or 60)
    https_enabled = _yaml_scalar_str(bool(https_cfg.get("enabled", True)))
    https_cert = _yaml_scalar_str(https_cfg.get("cert_content", ""))
    https_key = _yaml_scalar_str(https_cfg.get("key_content", ""))
    https_auto_redirect = _yaml_scalar_str(bool(https_cfg.get("auto_redirect", True)))
    https_redirect_port = _yaml_scalar_str(https_cfg.get("redirect_port", ""))
    https_domain = _yaml_scalar_str(https_cfg.get("domain", ""))
    username = _yaml_scalar_str(auth.get("username", "admin"))
    password_hash = _yaml_scalar_str(auth.get("password_hash", ""))
    totp_enabled = _yaml_scalar_str(bool(auth.get("totp_enabled", False)))
    totp_secret = _yaml_scalar_str(auth.get("totp_secret", ""))
    last_login_time = _yaml_scalar_str(auth.get("last_login_time", ""))
    last_login_ip = _yaml_scalar_str(auth.get("last_login_ip", ""))
    if not disabled:
        disabled_yaml = "[]"
    else:
        disabled_yaml = "[" + ", ".join(_yaml_scalar_str(e) for e in disabled) + "]"
    if not detected:
        detected_yaml = "[]"
    else:
        detected_yaml = "[" + ", ".join(_yaml_scalar_str(e) for e in detected) + "]"
    L = []
    L.append("# ============================================================")
    L.append("# 用户配置文件（可读写）")
    L.append("# 此文件由框架自动维护，手工修改时请遵循格式规范")
    L.append("# 修改插件启用列表后，可通过 Web 后台热重启生效")
    L.append("# ============================================================")
    L.append("")
    L.append("# ---------- 系统信息（可选） ----------")
    L.append("system:")
    L.append("  name: " + name + "                # 自定义软件名称（空则使用内置默认值）")
    L.append("  version: " + version + "             # 自定义版本号（空则使用内置默认值）")
    L.append("  auto_logout_minutes: " + str(auto_logout) + "  # 自动退出时间（分钟）：无操作超过该时长自动退出；0=关闭")
    L.append("  timezone: " + timezone + "  # 时区（IANA 名，如 Asia/Shanghai）；「登录自动更新时区」开启时登录后按浏览器时区覆盖")
    L.append("  auto_update_timezone: " + auto_update_timezone + "  # 登录自动更新时区：true=每次登录用浏览器时区自动覆盖上面的 timezone；false=固定用上面的 timezone")
    L.append("  default_page_size: " + str(default_page_size) + "  # 表单默认翻页数据：表格每页显示条数（1~100）")
    L.append("")
    L.append("# ---------- 认证相关 ----------")
    L.append("# 【如何修改登录密码】")
    L.append("#   Web 端无改密入口，修改密码的唯一途径：在本段手动添加 auth.password_plain 并填入新密码 → 保存本文件 → 重启 EXE。")
    L.append("#     框架启动时检测到该字段会自动完成密码重置（PBKDF2-SHA256 写入 password_hash，同时重置 TOTP 双因素），")
    L.append("#     随后进程自动退出，password_plain 行已被自动删除；再次启动即可用新密码登录。")
    L.append("# 注意：")
    L.append("#   - 修改密码：在下方 auth 段手动添加 password_plain 并填入新密码 → 保存本文件 → 重启 EXE，")
    L.append("#     启动时自动将密码重置为 PBKDF2-SHA256 哈希并删除该行后退出，再次启动即可用新密码登录（详见上方说明）；")
    L.append("#   - username 固定为 admin，暂不支持修改用户名 / 多用户；")
    L.append("#   - password_hash 为 PBKDF2-SHA256 哈希（非明文），请勿手工填写，格式错误将导致无法登录；")
    L.append("#   - 默认密码 Admin@123!，立即修改。")
    L.append("auth:")
    L.append("  username: " + username + "       # 管理员用户名（固定为 admin，暂不支持多用户）")
    # 审查修复：password_plain 仅在「用户手动添加改密请求」时出现在文件中，
    # 重置完成后由 _check_password_reset 删除，不再无条件输出空行
    _pp = auth.get("password_plain")
    if _pp:
        L.append("  password_plain: " + _yaml_scalar_str(_pp) +
                 "   # 明文改密入口：保存并重启 EXE 即完成重置（重置后本行自动删除）")
    L.append("  password_hash: " + password_hash + "       # 密码哈希（PBKDF2-SHA256），首次启动自动生成")
    L.append("  totp_enabled: " + totp_enabled + "     # TOTP 双因素认证开关")
    L.append("  totp_secret: " + totp_secret + "         # TOTP 密钥（Base32，绑定时自动写入，加密存储）")
    # 审查修复：渲染器此前不输出 pending_totp_secret，导致「绑定待确认密钥」
    # 在任何一次配置保存后从文件中消失（进程内缓存掩盖了问题，重启后绑定流程断裂）
    _pending_totp = auth.get("pending_totp_secret")
    if _pending_totp:
        L.append("  pending_totp_secret: " + _yaml_scalar_str(_pending_totp) +
                 "  # TOTP 绑定待确认密钥（加密存储，验证成功后自动删除）")
    L.append("  last_login_time: " + last_login_time + " # 上次登录时间（ISO 8601）")
    L.append("  last_login_ip: " + last_login_ip + " # 上次登录 IP")
    L.append("")
    L.append("# ---------- 插件配置 ----------")
    L.append("# detected：每次启动自动重新扫描并写入「所有检测到的插件」（仅作记录，不参与启停判定）")
    L.append("# disabled：关闭列表，为空表示启用全部已发现插件；wiki 插件默认启用（不在关闭列表中）")
    L.append("plugins:")
    L.append("  detected: " + detected_yaml)
    L.append("  disabled: " + disabled_yaml + "          # 例如：[guardian] 表示停用 guardian 插件")
    L.append("")
    L.append("# ---------- 日志配置 ----------")
    L.append("logging:")
    L.append("  level: " + log_level + "            # 日志级别：DEBUG / INFO / WARNING / ERROR")
    L.append("  file: " + log_file + "  # 仅作路径说明：实际按天命名为 data/logs/YYYYMMDD-netcore.log")
    L.append("  max_bytes: " + str(log_max_bytes) + "      # 单文件最大字节数（10MB）")
    L.append("  backup_count: " + str(log_backup) + "         # 保留最近日志文件个数")
    L.append("  audit_log_retention_days: " + str(log_retention) + "   # 审计日志保留天数（启动时自动删除超期日志文件；")
    L.append("                                 # 0 或负数=关闭自动清理；「日志中心-清理」仍可手动全清）")
    L.append("")
    L.append("# ---------- 通知频率限制 ----------")
    L.append("notify:")
    L.append("  rate_limit:")
    L.append("    enabled: " + notify_enabled + "           # 是否启用通知发送频率限制")
    L.append("    min_interval_seconds: " + str(notify_interval) + "  # 同一渠道最小发送间隔（秒）")
    L.append("")
    L.append("# ---------- HTTPS 配置 ----------")
    L.append("# enabled=true 默认启用 HTTPS：未配置自定义证书时自动生成自签名证书（data/certs/），")
    L.append("# 可在「系统设置-基础设置」上传自定义证书（.crt/.pem 证书 + .key 私钥），")
    L.append("# 上传后证书/私钥内容（PEM 文本）直接写入下方 cert_content/key_content，重启后生效。")
    L.append("https:")
    L.append("  enabled: " + https_enabled + "               # 是否启用 HTTPS（默认启用）")
    L.append("  cert_content: " + https_cert + "   # 自定义证书 PEM 文本（空=自动生成自签名）")
    L.append("  key_content: " + https_key + "    # 自定义私钥 PEM 文本（空=自动生成）")
    L.append("  auto_redirect: " + https_auto_redirect + "   # 自动转跳：启用 HTTPS 后误用 http 访问自动跳转 https；反之亦然（需重启生效）")
    L.append("  redirect_port: " + https_redirect_port + "   # 反向协议跳转监听端口（空=自动取主端口+1；可填具体端口）")
    L.append("  domain: " + https_domain + "   # HTTPS 证书 SAN 显式地址：留空=本机所有非回环网卡 IP；可填 IP 或域名，多个用逗号分隔（如 192.168.1.100,example.com），重启后生效")
    L.append("")
    # ---------- 安全开关（审查报告 #2/#3） ----------
    _sec = cfg.get("security", {}) or {}
    _enable_docs = _yaml_scalar_str(_sec.get("enable_docs", False))
    _trusted_proxies = _sec.get("trusted_proxies", ["127.0.0.1", "::1"]) or []
    L.append("# ---------- 安全开关 ----------")
    L.append("# enable_docs: Swagger/OpenAPI 文档是否开放（true=开放 /docs 和 /openapi.json；false=默认关闭，仅调试时开启）")
    L.append("# trusted_proxies: 反向代理可信对端 IP 列表，仅这些 IP 的 X-Forwarded-For 头会被信任（部署在 nginx 等反代后时需配置代理 IP）")
    L.append("security:")
    L.append("  enable_docs: " + _enable_docs)
    # 审查修复：IPv6（::1）在 YAML flow 序列中必须加引号，否则 ':' 导致解析失败
    tp_str = ", ".join('"%s"' % str(x) for x in _trusted_proxies) if _trusted_proxies else ""
    L.append("  trusted_proxies: [" + tp_str + "]")
    L.append("")
    L.append("# 说明：日志等级统一由上方 logging.level 控制（DEBUG/INFO/WARNING/ERROR）；")
    L.append("# 自动退出登录时间统一由上方 system.auto_logout_minutes 控制（0=关闭）。")
    return "\n".join(L) + "\n"


def _render_security_config_commented(cfg: dict) -> str:
    """带中文注释地重新渲染 security.yaml，保留当前值（白/黑名单条目不丢失）"""
    fp = cfg.get("failure_policy", {}) or {}
    whitelist = cfg.get("whitelist") or []
    blacklist = cfg.get("blacklist") or []
    max_failures = fp.get("max_failures", 5)
    block_minutes = fp.get("block_minutes", 10)
    reset_interval = fp.get("reset_interval_minutes", 30)

    def dump_list_block(lst):
        if not lst:
            return "[]"
        body = yaml.safe_dump(lst, allow_unicode=True, sort_keys=False).strip("\n")
        return "\n" + "\n".join("  " + ln for ln in body.split("\n"))

    L = []
    L.append("# ============================================================")
    L.append("# 安全策略配置文件（可读写）")
    L.append("# 修改后立即生效，无需重启服务")
    L.append("# ============================================================")
    L.append("")
    L.append("# ---------- 登录失败策略 ----------")
    L.append("failure_policy:")
    L.append("  max_failures: " + str(max_failures) + "         # 连续失败达到此次数后封禁")
    L.append("  block_minutes: " + str(block_minutes) + "       # 封禁时长（分钟）")
    L.append("  reset_interval_minutes: " + str(reset_interval) + "  # 失败计数重置间隔（分钟）")
    L.append("")
    L.append("# ---------- IP 白名单 ----------")
    L.append("# 受信任来源 IP（如管理员办公 IP），命中后直接放行且不受登录失败锁定策略约束；")
    L.append("# 不会因此限制其他正常用户访问。并非防火墙。")
    L.append('# 条目可带说明与有效期：{ip: "x.x.x.x", note: "管理员办公IP", expires_at: "2026-12-31T23:59:59"}')
    L.append("whitelist: " + dump_list_block(whitelist))
    L.append('  # - ip: "192.168.1.100"')
    L.append('  #   note: "管理员办公IP"')
    L.append('  #   expires_at: "2026-12-31T23:59:59"')
    L.append('  # - "10.0.0.0/8"')
    L.append("")
    L.append("# ---------- IP 黑名单 ----------")
    L.append("# 自动封禁或手动添加；命中且在封禁期内返回 404 以隐藏存在。")
    L.append("blacklist: " + dump_list_block(blacklist))
    L.append('  # - ip: "203.0.113.45"')
    L.append('  #   block_until: "2026-07-07T10:30:00Z"')
    L.append('  #   reason: "连续5次失败"')
    L.append('  #   note: "可疑扫描"')
    L.append('  #   fail_count: 5')
    return "\n".join(L) + "\n"


def _render_notify_config_commented(cfg: dict) -> str:
    """带中文注释地重新渲染 notify.yaml，保留当前值（避免 safe_dump 抹除中文注释）。

    此前 save_notify_config 用 yaml.safe_dump 整文件重写，Web 后台每保存一次
    通知配置，notify.yaml 的中文注释就全部丢失。现改为逐渠道带注释渲染。
    """
    templates = cfg.get("templates") if isinstance(cfg.get("templates"), dict) else {}
    email = cfg.get("email") if isinstance(cfg.get("email"), dict) else {}
    wechat = cfg.get("wechat_work") if isinstance(cfg.get("wechat_work"), dict) else {}
    dingtalk = cfg.get("dingtalk") if isinstance(cfg.get("dingtalk"), dict) else {}
    feishu = cfg.get("feishu") if isinstance(cfg.get("feishu"), dict) else {}

    def scalar(v, default=""):
        return _yaml_scalar_str(v if v is not None else default)

    def list_scalar(v, default=()):
        v = v if isinstance(v, list) else list(default)
        if not v:
            return "[]"
        return "[" + ", ".join(_yaml_scalar_str(x) for x in v) + "]"

    L = []
    L.append("# ============================================================")
    L.append("# 通知管理配置（可读写）")
    L.append("# 作用：配置系统的各类通知渠道（邮件 / 企业微信 / 钉钉 / 飞书），")
    L.append("#       用于向管理员推送设备告警、配置备份失败、任务完成等消息。")
    L.append("# 说明：")
    L.append("#   1. 密码、Webhook URL 等敏感字段使用 AES-256-GCM 加密存储，")
    L.append("#      手工填写明文会在首次读取时自动加密落盘；")
    L.append("#   2. 修改本文件后**立即生效**（无需重启程序），也可通过")
    L.append("#      「系统设置-通知管理」Web 后台进行可视化配置；")
    L.append("#   3. 渠道 enabled 为 false 时不发送任何消息（默认全部关闭）。")
    L.append("# ============================================================")
    L.append("")
    L.append("# ---------- 全局消息模板 ----------")
    L.append("# 可被各渠道引用（Go template 语法），支持以下变量：")
    L.append("#   {{.Title}}    消息标题（如\"设备告警：核心交换机A\"）")
    L.append("#   {{.Content}}  消息正文内容")
    L.append("#   {{.Priority}} 优先级（high / normal / low）")
    L.append("#   {{.Time}}     触发时间")
    L.append("#   {{.Source}}   消息来源（如\"数通配置卫士\"）")
    L.append("# 渠道配置里的 template 字段填哪个模板 id，就用哪个模板渲染消息。")
    L.append("templates:")
    for tid in ("default", "alert", "info"):
        tpl = templates.get(tid)
        if tpl is None:
            tpl = {"default": "{{if eq .Priority \"high\"}}[紧急] {{end}}{{.Title}}\n时间：{{.Time}}\n来源：{{.Source}}\n{{.Content}}",
                   "alert": "**告警通知**\n> 标题：{{.Title}}\n> 优先级：{{.Priority}}\n> 时间：{{.Time}}\n> 来源：{{.Source}}\n{{.Content}}",
                   "info": "信息通知：{{.Title}}\n{{.Content}}"}.get(tid, "")
        tip = {"default": "# default：通用模板——高优先级消息自动加[紧急]前缀",
               "alert": "# alert：告警模板——适合设备告警类消息，以醒目格式展示",
               "info": "# info：信息模板——普通通知消息"}[tid]
        L.append("  " + tip)
        L.append("  %s: |" % tid)
        for ln in str(tpl).split("\n"):
            L.append("    " + (ln if ln else ""))
    L.append("")
    L.append("# ---------- 邮件渠道（SMTP） ----------")
    L.append("# 适用场景：发送备份报告、周期性汇总邮件。")
    L.append("# 需要你有可用的 SMTP 服务器（如企业邮箱、QQ 邮箱、163 邮箱）。")
    L.append("email:")
    L.append("  enabled: %s" % scalar(email.get("enabled"), False) + "                    # 是否启用邮件渠道（true=启用 / false=停用）")
    L.append("  smtp_host: %s" % scalar(email.get("smtp_host")) + "                     # SMTP 服务器地址（如 smtp.qq.com、smtp.163.com）")
    L.append("  smtp_port: %s" % scalar(email.get("smtp_port"), 465) + "                    # SMTP 端口：465=SSL 加密 / 587=STARTTLS（选其一）")
    L.append("  smtp_ssl: %s" % scalar(email.get("smtp_ssl"), True) + "                    # 是否使用 SSL 加密（true=465端口SSL / false=587端口STARTTLS）")
    L.append("  username: %s" % scalar(email.get("username")) + "                      # 发件人邮箱账号（如 admin@example.com）")
    L.append("  password: %s" % scalar(email.get("password")) + "                      # 发件人邮箱密码 / 授权码（敏感字段，加密存储）")
    L.append("  sender_name: %s" % scalar(email.get("sender_name"), "NetCore Framework") + "  # 发件人显示名称（收件人看到的发件人名字）")
    L.append("  default_recipients: %s" % list_scalar(email.get("default_recipients")) + "        # 默认收件人列表，如 [\"a@example.com\", \"b@example.com\"]")
    L.append("  cc: %s" % list_scalar(email.get("cc")) + "                            # 默认抄送人列表（可选，留空表示不抄送）")
    L.append("  bcc: %s" % list_scalar(email.get("bcc")) + "                           # 默认密送人列表（可选，留空表示不密送）")
    L.append("  priority: %s" % scalar(email.get("priority"), "normal") + "               # 该渠道消息优先级：high / normal / low")
    L.append("  template: %s" % scalar(email.get("template"), "default") + "               # 使用的消息模板 id（见上方 templates）")
    L.append("")
    L.append("# ---------- 企业微信渠道 ----------")
    L.append("# 适用场景：通过企业微信群机器人推送告警，手机端实时收到。")
    L.append("# 配置方法：在企业微信群 → 添加群机器人 → 复制 Webhook 地址填入下方。")
    L.append("wechat_work:")
    L.append("  enabled: %s" % scalar(wechat.get("enabled"), False) + "                    # 是否启用企业微信渠道（true=启用 / false=停用）")
    L.append("  webhook_url: %s" % scalar(wechat.get("webhook_url")) + "                # 群机器人 Webhook 地址（敏感字段，加密存储）")
    L.append("  priority: %s" % scalar(wechat.get("priority"), "normal") + "               # 该渠道消息优先级：high / normal / low")
    L.append("  template: %s" % scalar(wechat.get("template"), "default") + "               # 使用的消息模板 id（见上方 templates）")
    L.append("")
    L.append("# ---------- 钉钉渠道 ----------")
    L.append("# 适用场景：通过钉钉群机器人推送告警，手机端实时收到。")
    L.append("# 配置方法：钉钉群 → 群设置 → 智能群助手 → 添加自定义机器人（选择\"加签\"方式），")
    L.append("#           将 Webhook 地址与加签密钥填入下方。")
    L.append("dingtalk:")
    L.append("  enabled: %s" % scalar(dingtalk.get("enabled"), False) + "                    # 是否启用钉钉渠道（true=启用 / false=停用）")
    L.append("  webhook_url: %s" % scalar(dingtalk.get("webhook_url")) + "                # 自定义机器人 Webhook 地址（敏感字段，加密存储）")
    L.append("  secret: %s" % scalar(dingtalk.get("secret")) + "                         # 加签密钥（安全设置选\"加签\"时必填；敏感字段，加密存储）")
    L.append("  priority: %s" % scalar(dingtalk.get("priority"), "normal") + "               # 该渠道消息优先级：high / normal / low")
    L.append("  template: %s" % scalar(dingtalk.get("template"), "default") + "               # 使用的消息模板 id（见上方 templates）")
    L.append("")
    L.append("# ---------- 飞书渠道 ----------")
    L.append("# 适用场景：通过飞书群机器人推送告警，手机端实时收到。")
    L.append("# 配置方法：飞书群 → 设置 → 群机器人 → 添加自定义机器人（选择\"签名校验\"方式），")
    L.append("#           将 Webhook 地址与签名密钥填入下方。")
    L.append("feishu:")
    L.append("  enabled: %s" % scalar(feishu.get("enabled"), False) + "                    # 是否启用飞书渠道（true=启用 / false=停用）")
    L.append("  webhook_url: %s" % scalar(feishu.get("webhook_url")) + "                # 自定义机器人 Webhook 地址（敏感字段，加密存储）")
    L.append("  secret: %s" % scalar(feishu.get("secret")) + "                         # 签名校验密钥（安全设置选\"签名校验\"时必填；敏感字段，加密存储）")
    L.append("  priority: %s" % scalar(feishu.get("priority"), "normal") + "               # 该渠道消息优先级：high / normal / low")
    L.append("  template: %s" % scalar(feishu.get("template"), "default") + "               # 使用的消息模板 id（见上方 templates）")
    return "\n".join(L) + "\n"


def get_core_config() -> dict:
    """读取核心配置（带缓存）"""
    if "core" not in _config_cache:
        _config_cache["core"] = _read_yaml(CONFIG_DIR / "core.yaml")
    return _config_cache["core"]


def get_user_config() -> dict:
    """读取用户配置（带缓存）

    注意：若配置文件尚不存在（例如 bootstrap 期间、_write_default_configs 尚未写出），
    _read_yaml 会返回 {}。此时【绝不能】把空字典缓存起来，否则后续调用（如
    refresh_detected_plugins）会读到被污染的空配置并 save_user_config({})，从而把
    刚写入的 password_hash / auth 等字段整体抹掉。因此仅当读到非空内容时才写缓存。
    """
    if "user" not in _config_cache:
        with _config_cache_lock:
            if "user" not in _config_cache:  # 双重检查，避免并发重复读盘
                data = _read_yaml(CONFIG_DIR / "user_config.yaml")
                if data:
                    _config_cache["user"] = data
    return _config_cache.get("user", {})


def get_security_config() -> dict:
    """读取安全配置（带缓存，双重检查锁）"""
    if "security" not in _config_cache:
        with _config_cache_lock:
            if "security" not in _config_cache:
                data = _read_yaml(CONFIG_DIR / "security.yaml")
                if data:
                    _config_cache["security"] = data
    return _config_cache.get("security", {})


def get_notify_config() -> dict:
    """读取通知配置（带缓存，双重检查锁）"""
    if "notify" not in _config_cache:
        with _config_cache_lock:
            if "notify" not in _config_cache:
                data = _read_yaml(CONFIG_DIR / "notify.yaml")
                if data:
                    _config_cache["notify"] = data
    return _config_cache.get("notify", {})


def _restrict_if_https_key_present(cfg: dict):
    """配置中存有 HTTPS 私钥（key_content）时，每次保存后重新收紧文件权限。

    审查修复：此前 _restrict_file_perms 仅在首次创建 user_config.yaml 时执行，
    后续上传证书/私钥重写文件后权限不再保证。icacls 开销可接受（仅含私钥时触发）。
    """
    try:
        https = cfg.get("https") if isinstance(cfg.get("https"), dict) else {}
        if https.get("key_content"):
            _restrict_file_perms(CONFIG_DIR / "user_config.yaml")
    except Exception as exc:
        try:
            from core.logger import get_logger
            get_logger().debug("收紧 user_config.yaml 权限失败：%s", exc)
        except Exception:  # noqa: BLE001
            pass


def save_user_config(cfg: dict):
    """保存用户配置并刷新缓存（保留中文注释，原子写入+并发保护）"""
    with _cfg_locks["user"]:
        _atomic_write_text(CONFIG_DIR / "user_config.yaml", _render_user_config_commented(cfg))
        _config_cache["user"] = cfg
    _restrict_if_https_key_present(cfg)


def update_user_config(mutator) -> dict:
    """审查报告 #4：受锁保护的读-改-写统一入口。

    以磁盘为准读取（避免缓存漂移），执行 mutator 修改，原子写回并刷新缓存。
    返回更新后的配置。散落的 get→改→save 序列应逐步收敛到本函数，避免并发丢更新。
    """
    with _cfg_locks["user"]:
        cfg = _read_yaml(CONFIG_DIR / "user_config.yaml") or {}
        mutator(cfg)
        _atomic_write_text(CONFIG_DIR / "user_config.yaml", _render_user_config_commented(cfg))
        _config_cache["user"] = cfg
    _restrict_if_https_key_present(cfg)
    return cfg


def save_security_config(cfg: dict):
    """保存安全配置并刷新缓存（保留中文注释，原子写入+并发保护）"""
    with _cfg_locks["security"]:
        _atomic_write_text(CONFIG_DIR / "security.yaml", _render_security_config_commented(cfg))
        _config_cache["security"] = cfg


def save_notify_config(cfg: dict):
    """保存通知配置并刷新缓存（保留中文注释，原子写入+并发保护）"""
    with _cfg_locks["notify"]:
        _atomic_write_text(CONFIG_DIR / "notify.yaml", _render_notify_config_commented(cfg))
        _config_cache["notify"] = cfg


def get_encryption_key() -> str:
    """获取 AES-256-GCM 加密密钥"""
    return get_core_config().get("crypto", {}).get("encryption_key", "")


# 传输派生密钥进程内缓存（主密钥运行期不变，派生值亦不变）
_transport_key_cache = None


def get_transport_encryption_key() -> str:
    """返回「传输加密」派生密钥（Base64，32 字节）。

    审查修复：登录前端必须先于登录拿到密钥才能加密凭证，因此该密钥只能经
    无鉴权接口 /api/system/crypto-key 下发——等于公开信息。此前直接下发静态
    主密钥 crypto.encryption_key，而该主密钥同时用于加密**落盘**的 TOTP secret
    与通知渠道密码/Webhook，任何能访问端口的人拿到它即可离线解密全部密文。

    现改为 HMAC-SHA256(主密钥, "netcore-transport-v1") 派生出独立传输子密钥：
      - 下发的仅是子密钥，泄露后无法解密任何落盘密文（主密钥永不出配置文件）；
      - 前端登录加密与 auth.decrypt_field 使用同一子密钥，协议与报文格式不变；
      - 兼容期：decrypt_field 会先试子密钥、再回落主密钥（旧缓存页面的请求）。
    """
    global _transport_key_cache
    if _transport_key_cache:
        return _transport_key_cache
    master_raw = base64.b64decode(get_encryption_key())
    digest = hmac.new(master_raw, b"netcore-transport-v1", hashlib.sha256).digest()
    _transport_key_cache = base64.b64encode(digest).decode("utf-8")
    return _transport_key_cache


def get_system_info() -> dict:
    """获取系统名称与版本（硬编码默认值可被用户配置覆盖）"""
    user_cfg = get_user_config()
    system = user_cfg.get("system", {})
    name = system.get("name") or SYSTEM_NAME
    version = system.get("version") or SYSTEM_VERSION
    return {"name": name, "version": version}
