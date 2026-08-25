"""
framework.py - 框架主装配模块

功能：创建 FastAPI 应用，注册中间件、API 路由、插件路由与前端静态资源
程序启动时完成配置引导、日志初始化、插件加载
"""
import shutil
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import core.api as api
from core.audit import ctx_client_ip
from core.config_loader import BASE_DIR, FRONTEND_DIR, WIKI_DIR, PLUGINS_DIR, SYSTEM_VERSION, bootstrap
from core.logger import get_logger, setup_logger
from core.notify import get_notify_manager
from core.plugin_manager import get_plugin_manager
from core.security import get_security_manager

logger = get_logger()


# 提取资源时跳过的子目录：这些目录由运行时产生（SQLite 数据库、日志、字节码缓存），
# 不可被打包时的模板内容覆盖或删除，否则会导致用户数据丢失。
# 注意：必须**递归**生效（含插件目录内部的 data/），否则打包环境下每次启动都会
# 因 shutil.rmtree 整个插件目录而清空运行时数据库（v40 修复：设备重启丢失的根因）。
_EXTRACT_SKIP_SUBDIRS = {"data", "logs", "__pycache__"}


def _copy_tree_merge(src: Path, dst: Path) -> None:
    """递归合并拷贝：覆盖静态文件，但**永不删除/覆盖**跳过的运行时目录。

    与「先 rmtree 再 copytree」不同：合并方式下，插件目录内由运行时产生的
    `data/`（含 SQLite 数据库 `guardian.db`）、`logs/`、`__pycache__`
    会被 _EXTRACT_SKIP_SUBDIRS 跳过而原样保留，从而跨重启持久化用户数据。
    """
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in _EXTRACT_SKIP_SUBDIRS:
            # 运行时数据/日志/缓存：保留现有内容，绝不被打包模板覆盖或删除
            continue
        target = dst / item.name
        if item.is_dir():
            _copy_tree_merge(item, target)
        else:
            shutil.copy2(item, target)


def _sync_plugin_frontend_orphans(meipass: Path) -> None:
    """清理插件 frontend/ 目录中的孤儿 .js 文件（升级残留）。

    合并提取「只增不删」会导致新版本已删除的插件前端文件残留在程序目录，并被
    /api/plugins/frontend-manifest 目录扫描继续注入到页面。
    此处仅针对**插件 frontend 静态 JS**做精确同步删除，绝不触碰
    data/logs 等运行时目录，用户数据不受影响。
    """
    src_plugins = meipass / "plugins"
    dst_plugins = BASE_DIR / "plugins"
    if not (src_plugins.is_dir() and dst_plugins.is_dir()):
        return
    for dst_fe in dst_plugins.glob("*/frontend"):
        src_fe = src_plugins / dst_fe.parent.name / "frontend"
        src_names = {i.name for i in src_fe.iterdir()} if src_fe.is_dir() else set()
        for item in dst_fe.iterdir():
            if item.is_file() and item.suffix == ".js" and item.name not in src_names:
                try:
                    item.unlink()
                    logger.info("已清理升级残留前端文件：%s", item)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("清理残留前端文件 %s 失败：%s", item, exc)


def _extract_bundled_resources():
    """打包后运行，将内嵌的 frontend/wiki/plugins **合并**提取到程序目录

    单文件打包（PyInstaller --onefile）运行时会把资源解压到临时目录 _MEIPASS。
    框架的插件发现（discover）扫描的是程序目录下的 plugins/，因此需将插件目录
    也提取到 BASE_DIR，保证插件可被发现、配置可被读取、SQLite 数据库可被写入。

    本函数在模块导入早期执行（早于 create_app 与 bootstrap）。
    采用**递归合并拷贝**并跳过运行时 data/logs/__pycache__ 子目录（递归生效）：
    每次启动只更新静态代码/模板，而保留用户运行时数据（如设备数据库 guardian.db）。
    原实现对每个插件目录先 `shutil.rmtree` 再 `copytree`，会整体删除
    插件目录（含其内部的 data/），导致设备数据库每次重启被清空。
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    for name in ("frontend", "wiki", "plugins"):
        src = Path(meipass) / name
        dst = BASE_DIR / name
        if not src.exists():
            continue
        try:
            _copy_tree_merge(src, dst)
            logger.info("已提取资源：%s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("提取资源 %s 失败：%s", name, exc)
    # 升级场景：同步清理插件 frontend 中已被新版本移除的孤儿 JS
    try:
        _sync_plugin_frontend_orphans(Path(meipass))
    except Exception as exc:  # noqa: BLE001
        logger.warning("清理插件前端残留失败：%s", exc)


def _check_password_reset():
    """若 user_config 配置了 password_plain，则重置密码并退出"""
    from core.config_loader import get_user_config, save_user_config
    from core.crypto_utils import CryptoUtils

    cfg = get_user_config()
    plain = cfg.get("auth", {}).get("password_plain")
    if plain:
        cfg["auth"]["password_hash"] = CryptoUtils.hash_password(plain)
        cfg["auth"].pop("password_plain", None)
        # Issue4：修改密码后一并重置 TOTP，避免旧密钥/开关残留导致无法登录
        cfg["auth"]["totp_enabled"] = False
        cfg["auth"]["totp_secret"] = ""
        save_user_config(cfg)
        logger.info("检测到 password_plain，已重置密码并退出，请移除该字段后重新启动")
        raise SystemExit(0)


def create_app() -> FastAPI:
    """构建并配置 FastAPI 应用"""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bootstrap()
        # 关键：bootstrap 会生成 notify.yaml 等配置文件。
        # NotifyManager 在模块导入时即被实例化，若此时配置尚不存在会拿到空配置，
        # 因此必须在 bootstrap 之后重新加载，确保通知渠道与模板生效。
        try:
            get_notify_manager().reload()
        except Exception as exc:  # noqa: BLE001
            logger.warning("通知管理器重载失败：%s", exc)
        setup_logger()
        try:
            _check_password_reset()
        except SystemExit:
            raise
        # 重新初始化日志（提取资源后路径可能变化）
        setup_logger()
        # 加载插件并挂载路由
        pm = get_plugin_manager()
        pm.load_all()
        pm.mount_routes(app)
        for _st in pm.get_status():
            _rc = _st.get("route_count", 0)
            if _st.get("status") == "success" and _rc == 0:
                logger.warning("插件 %s 已启用但路由数为 0（API 将全部 404）：%s",
                               _st["name"], _st.get("error") or "get_routes 未返回路由")
            else:
                logger.info("插件 %s：状态=%s 路由数=%d", _st["name"], _st.get("status"), _rc)
        logger.info("NetCore Framework 启动完成，已加载 %d 个插件", len(pm.plugins))
        yield
        # ---- 关闭：插件清理（幂等，失败不阻断退出）----
        try:
            for entry in list(pm.plugins.values()):
                inst = entry.get("instance") if isinstance(entry, dict) else None
                if inst is not None and hasattr(inst, "on_unload"):
                    try:
                        inst.on_unload()
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass
        logger.info("NetCore Framework 已停止")

    # 版本号单点维护于 core/config_loader.SYSTEM_VERSION，避免两处硬编码不同步
    app = FastAPI(title="NetCore Framework", version=SYSTEM_VERSION, lifespan=lifespan)

    # ---- 中间件：审计客户端 IP + IP 黑白名单 ----
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        ctx_client_ip.set(client_ip)
        path = request.url.path
        # 放行登录相关与静态资源，避免白名单误锁
        skip = any(path.startswith(p) for p in (
            "/assets", "/api/system/crypto-key", "/api/auth/login",
            "/api/system/health", "/docs", "/openapi.json",
        ))
        if not skip:
            # check_ip 只会返回 ("allow", None) 或 ("deny_blacklist", 404)：
            # 白名单是「受信任放行 + 免登录失败锁定」，不是「仅白名单可访问」的
            # 防火墙模式，因此不存在 deny_whitelist 这种结果。
            # 旧代码里那条 `deny_whitelist -> 403` 分支永远不会命中（死分支），
            # 却让人误以为配置了白名单就会拦截其他所有 IP，故删除以保持两处逻辑自洽。
            # 返回码 code 由 check_ip 给出（黑名单固定 404，用于隐藏后台存在）。
            verdict, code = get_security_manager().check_ip(client_ip)
            if verdict == "deny_blacklist":
                return JSONResponse(status_code=code or 404, content={"detail": "Not Found"})
        _t0 = time.time()
        try:
            response = await call_next(request)
            logger.debug("HTTP %s %s -> %d (%.0fms)", request.method, path,
                         response.status_code, (time.time() - _t0) * 1000)
            return response
        except Exception:
            logger.debug("HTTP %s %s -> 异常 (%.0fms)", request.method, path,
                         (time.time() - _t0) * 1000)
            raise

    # 中间件：运维常用工具箱(opstoolbox) 禁止浏览器缓存任何信息----
    @app.middleware("http")
    async def ops_nocache_middleware(request: Request, call_next):
        response = await call_next(request)
        _p = request.url.path
        if _p.startswith("/api/opstoolbox") or _p.startswith("/plugin-assets/ops_toolbox"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            for _h in ("ETag", "Last-Modified"):
                if _h in response.headers:
                    del response.headers[_h]
        return response

    # ---- 注册 API 路由（统一加 /api 前缀，匹配前端与接口清单）----
    app.include_router(api.router_auth, prefix="/api")
    app.include_router(api.router_security, prefix="/api")
    app.include_router(api.router_notify, prefix="/api")
    app.include_router(api.router_audit, prefix="/api")
    app.include_router(api.router_system, prefix="/api")
    app.include_router(api.router_plugins, prefix="/api")

    # ---- 前端静态资源 ----
    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="assets")
    if WIKI_DIR.exists():
        app.mount("/wiki", StaticFiles(directory=str(WIKI_DIR)), name="wiki")

    if PLUGINS_DIR.exists():
        for _p in PLUGINS_DIR.iterdir():
            _fe = _p / "frontend"
            if _p.is_dir() and _fe.is_dir():
                app.mount(
                    "/plugin-assets/" + _p.name,
                    StaticFiles(directory=str(_fe)),
                    name="plugin-assets-" + _p.name,
                )

    # ---- SPA 入口与兜底路由 ----
    @app.get("/api/plugins/frontend-manifest")
    async def frontend_manifest():
        """返回所有插件 frontend/ 下的 JS 文件清单，供前端动态注入<script>。

        契约（见 wiki/05-插件开发指南.md）：
        - 插件在 plugins/<name>/frontend/ 放置页面脚本；
        - 每个脚本通过 window.NC.registerPage(id, component, title) 自注册页面；
        - 框架扫描该目录，按 /plugin-assets/<name>/<file> 暴露静态地址。
        """
        # URL 追加基于文件 mtime 的版本参数，插件 JS 一改动即自动失效浏览器缓存，
        manifest = []
        if PLUGINS_DIR.exists():
            for _p in sorted(PLUGINS_DIR.iterdir()):
                _fe = _p / "frontend"
                if _p.is_dir() and _fe.is_dir():
                    files = []
                    for f in sorted(_fe.glob("*.js")):
                        if not f.is_file():
                            continue
                        try:
                            _v = str(int(f.stat().st_mtime))
                        except OSError:
                            _v = "0"
                        files.append("/plugin-assets/" + _p.name + "/" + f.name + "?v=" + _v)
                    if files:
                        manifest.append({"name": _p.name, "files": files})
        return manifest

    @app.get("/")
    async def index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(status_code=200, content={"message": "NetCore Framework 运行中，但未找到前端文件"})

    # ---- SPA 404 兜底：非 API/静态资源路径统一返回 index.html（前端路由接管）----
    # 用异常处理器实现，仅在「无任何路由匹配(404)」时触发，绝不遮蔽已注册的
        # API / 插件路由；刷新子页面（如 /system/security、/wiki/view/xxx）时返回
        # index.html，由前端路由接管，避免出现 {"detail":"Not Found"}。
    @app.exception_handler(404)
    async def _not_found_handler(request: Request, exc):
        path = request.url.path
        # 仅对真正的 API / 静态资源路径返回 JSON 404；
        # /wiki/view/* 是前端 SPA 路由，应走 index.html 回退。
        if path.startswith(("/api", "/assets", "/docs", "/openapi.json")) or (
            path.startswith("/wiki") and not path.startswith("/wiki/view/")
        ):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return app


# 在 create_app 之前完成资源提取：bootstrap 会创建空目录，
# 若等到 startup 再提取，空目录将导致 `not dst.exists()` 判断失效而跳过。
_extract_bundled_resources()
app = create_app()
