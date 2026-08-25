# -*- coding: utf-8 -*-
"""core/https_utils.py - HTTPS 证书管理

设计：
- 配置文件 core.yaml 新增 https 段：enabled（默认 true）/ cert_file / key_file；
- enabled=true 且未配置自定义证书时，首次启动自动生成**自签名证书**
  （data/certs/server.crt + server.key，有效期 365 天），保证「默认启用 HTTPS」开箱可用；
- 基础设置页可上传自定义证书（.crt/.pem + .key，类型受限），上传后保存为
  data/certs/custom.crt / custom.key 并写入 user_config（cert_file/key_file 指向），
  重启服务后生效；
- 证书不可用/生成失败时回退 HTTP 并给出明确日志提示（不阻塞启动）。
"""
import logging
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from cryptography import x509

from core.config_loader import DATA_DIR, get_core_config, get_user_config, save_user_config

logger = logging.getLogger("netcore.https")

CERT_DIR = DATA_DIR / "certs"
SELF_CERT = CERT_DIR / "server.crt"
SELF_KEY = CERT_DIR / "server.key"
CUSTOM_CERT = CERT_DIR / "custom.crt"
CUSTOM_KEY = CERT_DIR / "custom.key"


def generate_self_signed(cert_path: Path, key_path: Path, days: int = 365) -> None:
    """用 cryptography 生成自签名证书（RSA-2048 / SHA-256）。

    （HTTPS 显示缺陷修复）：SAN 不再依赖 socket.getaddrinfo(socket.gethostname)
    收集地址（该方法在大量机器上只解析到 127.0.0.1，导致证书漏掉用户真实访问的局域网 IP）。
    改为由 _desired_san_identities() 统一计算：localhost/127.0.0.1 + 本机所有非回环网卡
    IP（直接枚举网卡，跨平台）+ https.domain 显式条目（IP 或域名）+ 强制纳入 server.host
    （若为具体 IP）。确保「通过局域网 IP 访问」时证书名称匹配，Chrome 不再拦截 /assets
    下的 CSS/JS，页面正常渲染。
    """
    import socket
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NetCore Framework")])

    san = _desired_san_identities()

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _file_ok(path) -> bool:
    try:
        return bool(path) and Path(path).is_file() and Path(path).stat().st_size > 0
    except OSError:
        return False


def _is_loopback_ip(ip: str) -> bool:
    """判断是否为回环地址（含 127.* / ::1 / 0.0.0.0 / ::）。"""
    if not ip:
        return True
    if ip.startswith("127.") or ip in ("::1", "0.0.0.0", "::"):
        return True
    try:
        return ip_address(ip).is_loopback
    except Exception:  # noqa: BLE001
        return False


def _enumerate_nic_ips() -> set:
    """返回本机所有非回环 IPv4/IPv6 地址（跨平台，纯 stdlib，不依赖 gethostname 解析）。

    （HTTPS 显示缺陷修复）：旧实现用 socket.getaddrinfo(socket.gethostname)
    收集地址，在大量机器上只解析到 127.0.0.1（hosts 把主机名指向回环），导致证书 SAN
    漏掉用户真正用来访问的局域网 IP，浏览器拒绝加载 /assets → 页面只剩文字。
    现改为直接枚举网卡地址（Windows: iphlpapi.GetAdaptersAddresses；Linux: ioctl
    SIOCGIFADDR + /proc/net/if_inet6），确保真实可达地址进入 SAN。
    """
    ips: set = set()
    for fn in (_win_nic_ips, _linux_nic_ips, _udp_probe_ips):
        try:
            ips |= fn()
        except Exception:  # noqa: BLE001
            pass
    return {ip for ip in ips if not _is_loopback_ip(ip)}


def _win_nic_ips() -> set:
    """Windows：通过 iphlpapi.GetAdaptersAddresses 枚举所有网卡单播地址。"""
    import ctypes
    from ctypes import POINTER, Structure, c_ulong, c_void_p, byref, cast
    ips: set = set()
    AF_INET = 2
    AF_INET6 = 23
    GAA_FLAG_SKIP_ANYCAST = 0x0002
    GAA_FLAG_SKIP_MULTICAST = 0x0004
    GAA_FLAG_SKIP_DNS_SERVER = 0x0008

    class SOCKADDR(Structure):
        _fields_ = [("sa_family", ctypes.c_ushort), ("sa_data", ctypes.c_byte * 14)]

    class SOCKET_ADDRESS(Structure):
        _fields_ = [("lpSockaddr", POINTER(SOCKADDR)), ("iSockaddrLength", ctypes.c_int)]

    class IP_ADAPTER_UNICAST_ADDRESS(Structure):
        pass

    IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
        ("Length", c_ulong),
        ("Flags", c_ulong),
        ("Next", POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("Address", SOCKET_ADDRESS),
    ]

    class IP_ADAPTER_ADDRESSES(Structure):
        _fields_ = [
            ("Length", c_ulong),
            ("IfIndex", c_ulong),
            ("Next", POINTER(IP_ADAPTER_ADDRESSES)),
            ("AdapterName", c_void_p),
            ("FirstUnicastAddress", POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ]

    iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
    flags = GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER
    size = ctypes.c_ulong(15000)
    buf = ctypes.create_string_buffer(size.value)
    for _ in range(4):
        ret = iphlpapi.GetAdaptersAddresses(0, flags, None, buf, byref(size))
        if ret == 0:
            break
        if ret == 111:  # ERROR_BUFFER_OVERFLOW
            buf = ctypes.create_string_buffer(size.value)
        else:
            return ips
    else:
        return ips
    adv = cast(buf, POINTER(IP_ADAPTER_ADDRESSES))
    while adv:
        ua = adv.contents.FirstUnicastAddress
        while ua:
            sa = ua.contents.Address.lpSockaddr
            fam = sa.contents.sa_family
            data = cast(sa, POINTER(ctypes.c_ubyte * 16)).contents
            if fam == AF_INET:
                addr = ".".join(str(b) for b in data[4:8])
                if addr:
                    ips.add(addr)
            elif fam == AF_INET6:
                raw = bytes(data[8:24])
                try:
                    ips.add(str(ip_address(raw)))
                except Exception:  # noqa: BLE001
                    pass
            ua = ua.contents.Next
        adv = adv.contents.Next
    return ips


def _linux_nic_ips() -> set:
    """Linux：ioctl SIOCGIFADDR 枚举 IPv4 + /proc/net/if_inet6 枚举 IPv6。"""
    ips: set = set()
    try:
        import fcntl
        import struct
        import array
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        max_possible = 128
        bytesif = max_possible * 32
        names = array.array("B", b"\0" * bytesif)
        out = struct.unpack(
            "iL",
            fcntl.ioctl(
                s.fileno(), 0x8912,  # SIOCGIFCONF
                struct.pack("iL", bytesif, names.buffer_info()[0]),
            ),
        )
        namestr = names.tobytes()
        for i in range(0, out[0], 40):
            ips.add(socket.inet_ntoa(namestr[i + 20:i + 24]))
        s.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        with open("/proc/net/if_inet6") as f:
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                addr_hex = parts[0]
                groups = [addr_hex[i:i + 4] for i in range(0, 32, 4)]
                ips.add(":".join(groups))
    except Exception:  # noqa: BLE001
        pass
    return ips


def _udp_probe_ips() -> set:
    """兜底：UDP 连接到公网地址，取默认出口 IP（仅一个，保证至少拿到一个可用地址）。"""
    ips: set = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip:
            ips.add(ip)
    except Exception:  # noqa: BLE001
        pass
    return ips


def _split_entries(s: str) -> list:
    """把 domain 配置（逗号/分号/空格/换行分隔的多个 IP 或域名）拆成列表。"""
    return [p.strip() for p in re.split(r"[,\s;]+", s or "") if p.strip()]


def _to_san_value(entry: str):
    """将单个条目转成 SAN 值：能解析为 IP 则作 IPAddress，否则作 DNSName。"""
    try:
        return x509.IPAddress(ip_address(entry))
    except Exception:  # noqa: BLE001
        return x509.DNSName(entry)


def _cert_san_identities(cert_path) -> set:
    """读取证书 SAN 中所有 (类型, 值) 集合；读取失败返回空集合。"""
    try:
        data = Path(cert_path).read_bytes()
        cert = x509.load_pem_x509_certificate(data)
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        return {(type(g).__name__, str(g.value)) for g in ext.value}
    except Exception:  # noqa: BLE001
        return set()


def _desired_san_identities():
    """计算证书「应当包含的」全部 SAN 标识（IP/DNS）。

    - localhost / 127.0.0.1 始终包含（本地访问与转跳服需要）；
    - 若配置了 https.domain（可填 IP 或域名，多个用逗号分隔）→ 使用显式条目；
    - 否则 → 枚举本机所有非回环网卡 IP（默认行为）；
    - 强制纳入 core.yaml server.host（若为具体 IP），确保监听地址一定在证书中；
    - 主机名作为 DNS 兜底（便于按主机名访问）。
    """
    ids = [x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1"))]
    https_cfg = _https_config()
    domain = (https_cfg.get("domain") or "").strip()
    if domain:
        for entry in _split_entries(domain):
            ids.append(_to_san_value(entry))
    else:
        for ip in _enumerate_nic_ips():
            try:
                ids.append(x509.IPAddress(ip_address(ip)))
            except Exception:  # noqa: BLE001
                pass
    # 强制纳入 server.host（若为具体 IP/域名）
    try:
        host = (((get_core_config() or {}).get("server", {}) or {}).get("host", "") or "")
        if host and host not in ("0.0.0.0", "", "::"):
            try:
                ids.append(x509.IPAddress(ip_address(host)))
            except Exception:  # noqa: BLE001
                ids.append(x509.DNSName(host))
    except Exception:  # noqa: BLE001
        pass
    # 主机名兜底（便于按主机名访问）
    try:
        hn = socket.gethostname()
        if hn and hn not in ("localhost",):
            ids.append(x509.DNSName(hn))
    except Exception:  # noqa: BLE001
        pass
    seen = set()
    uniq = []
    for g in ids:
        key = (type(g).__name__, str(g.value))
        if key not in seen:
            seen.add(key)
            uniq.append(g)
    return uniq


def _self_cert_needs_regen(cert_path, key_path) -> bool:
    """自签名证书是否需要重新生成：文件缺失，或当前 SAN 未覆盖期望地址集合。

    （HTTPS 显示缺陷修复）：改用 _desired_san_identities 全量比对，
    任一期望地址（网卡 IP / domain / server.host）未出现在证书 SAN 中即重新生成，
    确保用户改用局域网 IP、填写 domain、或改监听地址后证书都能覆盖。
    """
    if not (_file_ok(cert_path) and _file_ok(key_path)):
        return True
    desired = {(type(g).__name__, str(g.value)) for g in _desired_san_identities()}
    if not desired:
        return False
    return not desired.issubset(_cert_san_identities(cert_path))


def _https_config() -> dict:
    """读取 https 配置： 起 https 段位于 user_config.yaml（可读写），
    core.yaml 仅作旧实例回退。：自定义证书/私钥以 **PEM 文本**
    （cert_content/key_content）存储于配置，不再保存文件路径。"""
    ucfg = get_user_config() or {}
    u_https = ucfg.get("https") if isinstance(ucfg.get("https"), dict) else {}
    c_https = (get_core_config() or {}).get("https") or {}
    merged = dict(c_https)
    merged.update({k: v for k, v in (u_https or {}).items() if v is not None})
    return merged


def ensure_certificate() -> tuple:
    """确保 HTTPS 证书可用，返回 (cert_file, key_file, ok)。

    优先级：配置中的 PEM 文本（cert_content/key_content，写入 data/certs/ 临时文件）
            > 旧版上传文件（data/certs/custom.*，兼容历史数据）> 自动生成自签名。
    """
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    https = _https_config()
    cert_text = (https.get("cert_content") or "").strip()
    key_text = (https.get("key_content") or "").strip()
    if cert_text and key_text:
        try:
            CERT_DIR.mkdir(parents=True, exist_ok=True)
            cert_p = CERT_DIR / "custom-content.crt"
            key_p = CERT_DIR / "custom-content.key"
            cert_p.write_text(cert_text, encoding="utf-8")
            key_p.write_text(key_text, encoding="utf-8")
            return str(cert_p), str(key_p), True
        except Exception as exc:  # noqa: BLE001
            logger.error("写入配置内证书/私钥文本失败，回退其他来源：%s", exc)
    # 2) 旧版上传保存的文件（data/certs/custom.*，兼容历史实例）
    if _file_ok(CUSTOM_CERT) and _file_ok(CUSTOM_KEY):
        return str(CUSTOM_CERT), str(CUSTOM_KEY), True
    # 3) 自动生成自签名（幂等：已存在且覆盖当前局域网地址则复用，否则重新生成）
    try:
        if _self_cert_needs_regen(SELF_CERT, SELF_KEY):
            try:
                SELF_CERT.unlink(missing_ok=True)
                SELF_KEY.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
            generate_self_signed(SELF_CERT, SELF_KEY)
            logger.info("已（重新）生成自签名证书：%s / %s", SELF_CERT, SELF_KEY)
        return str(SELF_CERT), str(SELF_KEY), True
    except Exception as exc:  # noqa: BLE001
        logger.error("自签名证书生成失败：%s", exc)
        return "", "", False


def ensure_https_context() -> dict:
    """读取 https 配置，返回 uvicorn.run 的 ssl 参数 dict；未启用/不可用时返回 {}（HTTP）。"""
    https = _https_config()
    enabled = bool(https.get("enabled", True))
    if not enabled:
        return {}
    cert, key, ok = ensure_certificate()
    if not ok:
        logger.warning("HTTPS 已启用但证书不可用，本次以 HTTP 启动（可上传证书后重启）")
        return {}
    return {"ssl_certfile": cert, "ssl_keyfile": key}


def save_uploaded_cert(cert_data: bytes, key_data: bytes) -> tuple:
    """保存上传的自定义证书/私钥。

    不再保存到 data/certs/custom.* 并记录路径（文件易随目录清理
    或迁移丢失），改为把证书/私钥内容解码为 PEM 文本直接写入 user_config.yaml 的
    https.cert_content / https.key_content，配置即证书本体，重启后由 ensure_certificate
    写出临时文件供 uvicorn 加载。
    """
    def _decode(b: bytes) -> str:
        for enc in ("utf-8", "latin-1"):
            try:
                return b.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return b.decode("utf-8", "replace")

    cert_text = _decode(cert_data).strip()
    key_text = _decode(key_data).strip()
    if not cert_text or not key_text:
        raise ValueError("上传内容为空")
    cfg = get_user_config() or {}
    if "https" not in cfg or not isinstance(cfg["https"], dict):
        cfg["https"] = {}
    cfg["https"]["cert_content"] = cert_text
    cfg["https"]["key_content"] = key_text
    cfg["https"].pop("cert_file", None)
    cfg["https"].pop("key_file", None)
    save_user_config(cfg)
    return "配置内存储（cert_content/key_content）", "配置内存储（cert_content/key_content）"
