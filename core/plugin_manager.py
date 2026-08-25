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
        """根据关闭列表加载所有插件（故障隔离）"""
        discovered = self.discover()
        disabled = get_user_config().get("plugins", {}).get("disabled") or []
        disabled_set = set(disabled)
        for name in discovered:
            if name in disabled_set:
                self.plugins[name] = {
                    "instance": None, "module": None, "status": "disabled",
                    "error": "", "metadata": {}, "routes": None, "menus": [],
                }
            else:
                self._load_plugin(name)

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
        # 优先读取 config/ 子目录下的插件配置；兼容旧版直接放在插件根目录的 config.yaml
        for candidate in (
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
        # 优雅关闭
        instance = entry.get("instance")
        if instance is not None:
            try:
                import threading as _t

                def _unload():
                    try:
                        instance.on_unload()
                    except Exception:  # noqa: BLE001
                        pass

                t = _t.Thread(target=_unload, daemon=True)
                t.start()
                t.join(timeout)
                if t.is_alive():
                    logger.warning("插件 %s 关闭超时（%d秒）", name, timeout)
            except Exception as exc:  # noqa: BLE001
                logger.warning("插件 %s 关闭异常：%s", name, exc)
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
        """将各插件的 APIRouter 挂载到 FastAPI 应用（幂等：基于已挂载集合防重）"""
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
