"""
plugin_manager.py - 插件管理器

功能：扫描、加载、热重启插件，单插件失败不影响主框架（故障隔离）
"""
import importlib
import threading
from pathlib import Path
from typing import Dict, List

import yaml

from core.config_loader import PLUGINS_DIR, get_user_config
from core.logger import get_logger
from plugins.base_plugin import BasePlugin

logger = get_logger()


class PluginManager:
    """插件管理器（单例）"""

    def __init__(self):
        # name -> {instance, module, status, error, metadata, routes, menus}
        self.plugins: Dict[str, dict] = {}
        self._lock = threading.Lock()
        # 记录**已挂载的 router id 集合**（APIRouter 不可哈希，
        # 用 id 标识）——plugin_toggle 启用插件时只 load_all 不 mount_routes，导致
        # 「菜单出现但 API 404」（wiki 文档全挂的根因）。mount_routes / mount_new_routes
        self._app = None
        self._mounted_routers = set()

    # ---------------- 发现 ----------------
    def discover(self) -> List[str]:
        """扫描 plugins/ 目录，返回包含 plugin.py 的插件名列表"""
        names = []
        if not PLUGINS_DIR.exists():
            return names
        for sub in sorted(PLUGINS_DIR.iterdir()):
            if sub.is_dir() and (sub / "plugin.py").exists():
                names.append(sub.name)
        return names

    # ---------------- 加载 ----------------
    def load_all(self):
        """根据关闭列表加载所有插件（故障隔离）

        审查修复：加载前先卸载现存实例。此前 plugin_toggle（运行期启停）调用
        本方法时，会对**所有**已启用插件再次执行 _load_plugin——重复实例化、
        二次触发 on_load（后台线程/调度任务成倍增加），且旧实例永不 on_unload。
        现统一「先卸旧、再装新」。
        注意：Starlette 无法在运行期摘除已 include 的路由，因此禁用插件后其
        API 路由仍会保留到下次重启；本方法保证的是**生命周期语义**正确
        （旧实例被关闭、新实例只加载一份），路由层语义见 mount_routes 注释。
        """
        # 审查修复：将程序目录 plugins（dist/plugins）挂入 plugins 包的模块搜索路径，
        # 使 EXE 打包之外手工部署的插件（独立仓库）也能被 importlib 找到。
        # 默认 plugins 包解析到打包内 _MEIPASS/plugins（仅框架自带插件），
        # 不挂载则外部插件 import 时报 No module named 'plugins.<name>'。
        try:
            import plugins as _plugins_pkg
            _p = str(PLUGINS_DIR)
            if _p not in [str(x) for x in _plugins_pkg.__path__]:
                _plugins_pkg.__path__.append(_p)
        except Exception as exc:  # noqa: BLE001
            logger.warning("挂载外部插件目录到 plugins 包失败：%s", exc)
        discovered = self.discover()
        disabled = get_user_config().get("plugins", {}).get("disabled") or []
        disabled_set = set(disabled)
        # 先优雅关闭全部现存实例，再清空注册表重新加载（避免重复实例与状态残留）
        with self._lock:
            existing = [
                e.get("instance") for e in self.plugins.values()
                if isinstance(e, dict)
            ]
            self.plugins.clear()
        for inst in existing:
            self._unload_instance(inst)
        for name in discovered:
            if name in disabled_set:
                self.plugins[name] = {
                    "instance": None, "module": None, "status": "disabled",
                    "error": "", "metadata": {}, "routes": None, "menus": [],
                }
            else:
                self._load_plugin(name)

    @staticmethod
    def _unload_instance(instance, timeout: int = 5):
        """优雅关闭单个插件实例（带超时、异常不阻断）。

        抽取自 reload()：load_all 与 reload 共用同一卸载路径。
        """
        if instance is None:
            return
        try:
            import threading as _t

            def _do():
                try:
                    instance.on_unload()
                except Exception:  # noqa: BLE001
                    pass

            th = _t.Thread(target=_do, daemon=True)
            th.start()
            th.join(timeout)
            if th.is_alive():
                logger.warning("插件 on_unload 超时（%d 秒），放弃等待", timeout)
        except Exception as exc:  # noqa: BLE001
            logger.warning("插件 on_unload 异常：%s", exc)

    def _load_plugin(self, name: str):
        try:
            module = importlib.import_module("plugins.%s.plugin" % name)
            cls = self._find_plugin_class(module)
            if cls is None:
                raise RuntimeError("未找到 BasePlugin 子类")
            cfg = self._load_plugin_config(name)
            instance = cls(name, cfg)
            ok = instance.on_load()
            routes = instance.get_routes()
            menus = instance.get_menus()
            with self._lock:
                self.plugins[name] = {
                    "instance": instance,
                    "module": module,
                    "status": "success" if ok else "failed",
                    "error": "" if ok else "on_load 返回 False",
                    "metadata": instance.get_metadata(),
                    "routes": routes,
                    "menus": menus or [],
                }
            logger.info("插件 %s 加载%s", name, "成功" if ok else "失败")
            logger.debug("插件 %s 详情：路由 %d 条 / 菜单 %d 项 / 版本 %s",
                         name, len(routes.routes) if routes is not None else 0,
                         len(menus or []),
                         (instance.get_metadata() or {}).get("version", ""))
        except Exception as exc:  # noqa: BLE001
            logger.error("插件 %s 加载失败：%s", name, exc)
            with self._lock:
                self.plugins[name] = {
                    "instance": None, "module": None, "status": "failed",
                    "error": str(exc), "metadata": {}, "routes": None, "menus": [],
                }

    @staticmethod
    def _find_plugin_class(module):
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                return obj
        return None

    @staticmethod
    def _load_plugin_config(name: str) -> dict:
        # 优先读取 data/ 子目录下的插件配置；兼容旧版 config/ 与根目录
        for candidate in (
            PLUGINS_DIR / name / "data" / "config.yaml",
            PLUGINS_DIR / name / "config" / "config.yaml",
            PLUGINS_DIR / name / "config.yaml",
        ):
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as handle:
                    return yaml.safe_load(handle) or {}
        return {}

    # ---------------- 热重启 ----------------
    def reload(self, name: str, timeout: int = 10) -> dict:
        """热重启单个插件（优雅关闭 + 重新加载）"""
        with self._lock:
            entry = self.plugins.get(name)
        if entry is None:
            return {"success": False, "message": "插件不存在"}
        # 优雅关闭（与 load_all 共用同一卸载路径）
        self._unload_instance(entry.get("instance"), timeout=timeout)
        # 重新加载模块
        try:
            module = entry.get("module")
            if module is not None:
                importlib.reload(module)
            else:
                module = importlib.import_module("plugins.%s.plugin" % name)
            cls = self._find_plugin_class(module)
            if cls is None:
                raise RuntimeError("未找到 BasePlugin 子类")
            cfg = self._load_plugin_config(name)
            new_instance = cls(name, cfg)
            ok = new_instance.on_load()
            new_routes = new_instance.get_routes()
            with self._lock:
                self.plugins[name] = {
                    "instance": new_instance,
                    "module": module,
                    "status": "success" if ok else "failed",
                    "error": "" if ok else "on_load 返回 False",
                    "metadata": new_instance.get_metadata(),
                    "routes": new_routes,
                    "menus": new_instance.get_menus() or [],
                }
            old_routes = entry.get("routes")
            if old_routes is None and new_routes is not None and self._app is not None:
                self.mount_new_routes()
            from core.audit import audit_log
            audit_log("plugin_reload", "插件:%s" % name, "success" if ok else "failed")
            return {"success": ok, "message": "重启%s" % ("成功" if ok else "失败")}
        except Exception as exc:  # noqa: BLE001
            logger.error("插件 %s 重启失败：%s", name, exc)
            with self._lock:
                self.plugins[name] = {
                    "instance": None, "module": None, "status": "failed",
                    "error": str(exc), "metadata": {}, "routes": None, "menus": [],
                }
            from core.audit import audit_log
            audit_log("plugin_reload", "插件:%s 失败:%s" % (name, exc), "failed")
            return {"success": False, "message": "重启失败：%s" % exc}

    def reload_all(self, timeout: int = 10) -> List[dict]:
        results = []
        for name in list(self.plugins.keys()):
            results.append({"plugin": name, **self.reload(name, timeout)})
        return results

    def reload_failed(self, timeout: int = 10) -> List[dict]:
        results = []
        with self._lock:
            failed = [n for n, e in self.plugins.items() if e.get("status") == "failed"]
        for name in failed:
            results.append({"plugin": name, **self.reload(name, timeout)})
        return results

    # ---------------- 查询 ----------------
    def get_status(self) -> List[dict]:
        from core.config_loader import get_user_config
        disabled_list = get_user_config().get("plugins", {}).get("disabled") or []
        disabled_set = set(disabled_list)
        with self._lock:
            out = []
            for name, entry in self.plugins.items():
                router = entry.get("routes")
                route_count = len(router.routes) if router is not None else 0
                out.append({
                    "name": name,
                    "status": entry.get("status"),
                    "error": entry.get("error", ""),
                    "metadata": entry.get("metadata", {}),
                    "enabled": name not in disabled_set,
                    "path": "plugins/" + name,
                    "route_count": route_count,
                })
            return out

    def get_menus(self) -> List[dict]:
        with self._lock:
            menus = []
            for name, entry in self.plugins.items():
                if entry.get("status") == "success":
                    menus.extend(entry.get("menus", []))
            return menus

    def mount_routes(self, app):
        """将各插件的 APIRouter 挂载到 FastAPI 应用（幂等：基于已挂载集合防重）

        路由语义（审查修复时明确）：Starlette 不支持运行期摘除已 include 的路由，
        因此「禁用插件」只影响生命周期（实例被卸载、不再加载），其已挂载的
        API 路由会保留到下次重启；同理，运行期 reload 成功后新 router 会追加
        到路由表尾部，旧 router 仍在前优先匹配——**路由级变更需重启完全生效**。
        本框架单用户内网工具的定位下，此限制可接受，但必须在文档/UI 中明示。
        """
        self._app = app
        with self._lock:
            for name, entry in self.plugins.items():
                router = entry.get("routes")
                if router is not None and id(router) not in self._mounted_routers:
                    try:
                        app.include_router(router)
                        self._mounted_routers.add(id(router))
                        logger.info("已挂载插件 %s 的路由", name)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("插件 %s 路由挂载失败：%s", name, exc)

    def mount_new_routes(self):
        """挂载**当前未挂载**的插件路由（幂等）。

        plugin_toggle / reload 等运行期重载插件后调用，解决「插件已启用（菜单出现）
        但路由未挂载 → API 404」（用户环境 wiki 文档全挂的根因）。
        """
        if self._app is None:
            return
        with self._lock:
            for name, entry in self.plugins.items():
                router = entry.get("routes")
                if router is not None and id(router) not in self._mounted_routers:
                    try:
                        self._app.include_router(router)
                        self._mounted_routers.add(id(router))
                        logger.info("已补挂插件 %s 的路由（运行期重载/启用）", name)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("插件 %s 路由补挂失败：%s", name, exc)


_plugin_manager = PluginManager()


def get_plugin_manager() -> PluginManager:
    return _plugin_manager
