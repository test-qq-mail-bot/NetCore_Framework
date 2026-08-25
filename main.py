"""
main.py - NetCore Framework 程序入口

功能：启动 Uvicorn 服务，加载框架与插件
既可作为 python main.py 开发运行，也可由 PyInstaller 打包为单文件 exe
"""
import asyncio
import sys
import socket
import threading

import uvicorn

from core.config_loader import get_core_config
from core.framework import app
from core.logger import get_logger, setup_logger
# 模块导入失败/不可用时回退 HTTP（不阻塞启动）
try:
    from core.https_utils import ensure_https_context as _ensure_https_context
except Exception:  # noqa: BLE001
    _ensure_https_context = None


# 统一日志格式：日期 + 时分秒，使用运行系统所在时区（logging.Formatter 默认用本地时区）


def _is_port_available(host: str, port: int) -> bool:
    """检测端口是否可绑定

    对通配 host（0.0.0.0 / 空）额外校验回环地址 127.0.0.1：
    Windows 下 0.0.0.0 与具体地址（如 127.0.0.1）的绑定语义不同，
    仅探测 0.0.0.0 可能误判为“可用”，但实际 127.0.0.1:port 已被其他进程占用，
    导致 uvicorn 绑定 0.0.0.0 成功、浏览器经 127.0.0.1 访问却命中对方进程
    （表现为“程序显示运行中但网页打不开 / 404”）。因此通配 host 必须
    0.0.0.0 与 127.0.0.1 同时可用，才视为真正可用。
    """
    hosts = ["0.0.0.0", "127.0.0.1"] if (host in ("0.0.0.0", "", None)) else [host]
    for h in hosts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                sock.bind((h, port))
        except OSError:
            return False
    return True


def _make_asyncio_exception_handler():
    """Windows 下客户端 keep-alive/心跳连接被对端
    正常断开时，asyncio 会以 ConnectionResetError(10054) 形式向异常回调处理器报告「回调
    异常」噪声（_ProactorBasePipeTransport._call_connection_lost）。返回一个异常处理器，
    过滤这类「连接被对端重置」的正常断开场景，其余异常照常按默认方式输出。

    注意：必须在**实际运行的事件循环**上设置才有效——旧实现 `asyncio.new_event_loop() +
    set_event_loop()` 会被 uvicorn.run 内部的 asyncio.run 新建的 loop 覆盖，处理器从未生效
    （用户控制台持续刷 ConnectionResetError 的根因）。 改为手动
    uvicorn.Config/Server，在 asyncio.run(_serve_with_exception_filter()) 里对 running loop
    设置本处理器。
    """
    def _handler(loop_, context):
        exc = context.get("exception")
        if exc is not None:
            name = type(exc).__name__
            if name == "ConnectionResetError" or "ConnectionResetError" in str(exc):
                return  # 客户端主动断开，属正常现象，静默
        loop_.default_exception_handler(context)
    return _handler


async def _serve_with_exception_filter(config: uvicorn.Config):
    """在 running loop 上挂接异常处理器后启动 uvicorn.Server。"""
    import asyncio
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_make_asyncio_exception_handler())
    server = uvicorn.Server(config)
    await server.serve()


def _run_redirect_server(host: str, port: int, main_scheme: str, main_port: int,
                         use_ssl: bool, log_level: str):
    """反向协议自动转跳服务。

    在独立线程运行：把误用另一协议访问本端口的请求以 307 重定向到主服务 URL
    （scheme/port 取主服务，host 取自客户端 Host 头，对远程访问也正确）。
    主服务是 HTTPS → 本跳转服用 HTTP；主服务是 HTTP → 本跳转服用 HTTPS（自签名证书，
    浏览器提示不安全属正常现象）。
    """
    import uvicorn as _uvicorn
    from starlette.applications import Starlette
    from starlette.responses import RedirectResponse
    from starlette.routing import Route

    async def _redirect(request):
        host_header = request.headers.get("host", "")
        client_host = host_header.split(":")[0] if host_header else "127.0.0.1"
        target = "%s://%s:%d%s" % (main_scheme, client_host, main_port, request.url.path)
        if request.url.query_string:
            target += "?" + request.url.query_string.decode()
        return RedirectResponse(url=target, status_code=307)

    redirect_app = Starlette(routes=[
        Route("/", _redirect),
        Route("/{path:path}", _redirect),
    ])
    ssl = {}
    if use_ssl:
        try:
            from core.https_utils import ensure_certificate
            _cert, _key, _ok = ensure_certificate()
            if _ok:
                ssl = {"ssl_certfile": _cert, "ssl_keyfile": _key}
        except Exception as exc:  # noqa: BLE001
            get_logger().warning("自动转跳 HTTPS 证书准备失败：%s", exc)
            return
    try:
        _cfg = _uvicorn.Config(redirect_app, host=host, port=port,
                               log_level=str(log_level or "info").lower(),
                               log_config=None, **ssl)
        _uvicorn.Server(_cfg).run()
    except Exception as exc:  # noqa: BLE001
        get_logger().warning("自动转跳服务异常退出：%s", exc)


def main():
    # 启动前先引导配置与日志
    setup_logger()
    logger = get_logger()
    cfg = get_core_config()
    server = cfg.get("server", {})
    host = server.get("host", "0.0.0.0")
    port = int(server.get("port", 8080))

    # 端口冲突自动顺延：若配置端口被占用，在控制台显示提示信息，并尝试 +1 ~ +20
    # 直到找到可用端口，避免本机常见服务（如华为 AgileController 占用 8080）导致程序启动失败
    original_port = port
    max_attempts = 20
    if not _is_port_available(host, port):
        print("=" * 60)
        print("[NetCore Framework] 端口冲突警告")
        print("  配置端口号: %d" % original_port)
        print("  监听地址: %s" % host)
        print("  该端口已被其他程序占用，正在尝试自动顺延...")
        logger.warning("端口 %d 已被占用（host=%s），尝试自动顺延", port, host)
        found = False
        for candidate in range(port + 1, port + 1 + max_attempts):
            if _is_port_available(host, candidate):
                port = candidate
                found = True
                break
        if not found:
            msg = (
                "端口 %d 及其后 %d 个端口均被占用，无法启动服务。"
                "请修改 config/core.yaml 中的 server.port 后重试。"
                % (original_port, max_attempts)
            )
            print("  [错误] %s" % msg)
            print("=" * 60)
            logger.error(msg)
            sys.exit(1)
        print("  已自动切换至端口: %d (原配置: %d)" % (port, original_port))
        print("  请在浏览器中访问 http://%s:%d" % (host if host != "0.0.0.0" else "127.0.0.1", port))
        print("=" * 60)
        logger.warning("已自动切换至端口 %d 启动（原配置端口 %d 被占用）", port, original_port)

    ssl_kwargs = {}
    https_mode = "http"
    try:
        if _ensure_https_context is not None:
            ssl_kwargs = _ensure_https_context()
            if ssl_kwargs:
                https_mode = "https"
    except Exception as exc:  # noqa: BLE001
        logger.warning("HTTPS 初始化异常，本次以 HTTP 启动：%s", exc)
        ssl_kwargs = {}

    from core.logger import get_level
    uv_log_level = str(get_level()).lower() if str(get_level()).lower() in ("debug", "info", "warning", "error", "critical") else "info"

    from core.config_loader import get_user_config as _get_user_config
    _ucfg = _get_user_config() or {}
    _https_cfg = _ucfg.get("https") if isinstance(_ucfg.get("https"), dict) else {}
    _auto_redirect = bool(_https_cfg.get("auto_redirect", True))
    _redirect_port_cfg = _https_cfg.get("redirect_port", "")
    _redirect_port = None
    _redirect_scheme = None
    if _auto_redirect:
        try:
            _rp = int(_redirect_port_cfg) if str(_redirect_port_cfg).strip() else (port + 1)
        except (TypeError, ValueError):
            _rp = port + 1
        if _is_port_available(host, _rp):
            _redirect_use_ssl = (https_mode == "http")  # 主 HTTP → 跳转服用 HTTPS，反之亦然
            _redirect_port = _rp
            _redirect_scheme = "https" if _redirect_use_ssl else "http"
            _t = threading.Thread(
                target=_run_redirect_server,
                args=(host, _rp, https_mode, port, _redirect_use_ssl, uv_log_level),
                daemon=True,
            )
            _t.start()
            logger.info("已启动自动转跳监听 %s://%s:%d → %s://%s:%d",
                        "https" if _redirect_use_ssl else "http", host, _rp, https_mode, host, port)
        else:
            logger.warning("自动转跳端口 %d 不可用，已跳过（仍可正常访问主端口 %d）", _rp, port)

    # 必须用内置值，避免用户自定义 version（如 "211"）掩盖真实框架版本。
    from core.config_loader import SYSTEM_NAME, SYSTEM_VERSION
    bind_host = host
    display_host = host
    print("=" * 60)
    print("[%s] 启动成功" % SYSTEM_NAME)
    print("  软件名: %s" % SYSTEM_NAME)
    print("  版本: %s" % SYSTEM_VERSION)
    print("  监听地址: %s://%s:%d" % (https_mode, display_host, port))
    if https_mode == "https":
        print("  提示: HTTPS 已启用（自签名证书浏览器会提示不安全，属正常现象；可上传自定义证书）")
    if _redirect_port is not None:
        print("  自动转跳: 已开启，误用 %s 访问 %s://%s:%d 会自动跳转至 %s://%s:%d"
              % ("HTTPS" if https_mode == "http" else "HTTP",
                 _redirect_scheme, display_host, _redirect_port, https_mode, display_host, port))
    print("=" * 60)
    logger.info("%s 启动中，内置版本 %s，监听 %s://%s:%d", SYSTEM_NAME, SYSTEM_VERSION, https_mode, bind_host, port)
    try:
        # 过滤 Windows 下客户端断开的 ConnectionResetError 回调噪声（旧 uvicorn.run 方案无效）
        config = uvicorn.Config(app, host=host, port=port,
                                log_level=uv_log_level,
                                # ERR_TOO_MANY_RETRIES（首屏仅文字无样式的根因类别）；纯 Python 的
                                http="h11",
                                log_config=None, **ssl_kwargs)
        asyncio.run(_serve_with_exception_filter(config))
    except OSError as exc:
        # 兜底：极少数情况下运行时端口被抢占，给出明确提示
        msg = "服务启动失败（绑定 %s:%d 出错）：%s" % (host, port, exc)
        logger.error(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
