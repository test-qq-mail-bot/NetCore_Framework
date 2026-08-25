"""
wiki/plugin_template/plugin.py - 空白插件模板

功能：供开发者复制使用的插件骨架，含完整中文注释
实现 BasePlugin 的四个抽象方法即可被框架加载
"""
from typing import Dict, List, Optional

from fastapi import APIRouter

from plugins.base_plugin import BasePlugin


class TemplatePlugin(BasePlugin):
    """插件模板：演示如何实现一个最小可用插件"""

    def get_metadata(self) -> Dict[str, str]:
        """返回插件元信息"""
        return {
            "name": self.name,
            "version": "1.0.0",
            "description": "插件模板",
            "author": "your-name",
        }

    def on_load(self) -> bool:
        """插件加载时执行，返回 True 表示成功"""
        # TODO: 在这里初始化数据库连接、加载配置、注册调度任务等
        return True

    def get_routes(self) -> Optional[APIRouter]:
        """注册 API 路由（返回 APIRouter 或 None）"""
        router = APIRouter()

        @router.get("/api/%s/hello" % self.name)
        async def hello():
            return {"plugin": self.name, "status": "ok"}

        return router

    def get_menus(self) -> List[Dict]:
        """向左侧菜单注册入口"""
        return [{
            "id": self.name,
            "label": "插件模板",
            "icon": "el-icon-box",
            "children": [
                {"id": "%s_home" % self.name, "label": "首页", "path": "/%s" % self.name},
            ],
        }]

    def on_unload(self):
        """优雅关闭：释放连接、停止任务等"""
        pass
