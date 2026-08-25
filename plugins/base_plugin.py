"""
base_plugin.py - 插件抽象基类

功能：定义所有插件必须实现的接口
框架通过标准接口与插件通信，插件内部错误由框架捕获
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from fastapi import APIRouter


class BasePlugin(ABC):
    """插件基类，所有业务插件需继承并实现抽象方法"""

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}
        self._loaded = False

    @abstractmethod
    def get_metadata(self) -> Dict[str, str]:
        """返回插件元信息（名称、版本、描述、作者）"""
        pass

    @abstractmethod
    def on_load(self) -> bool:
        """加载插件，返回 True/False"""
        pass

    @abstractmethod
    def get_routes(self) -> Optional[APIRouter]:
        """注册 API 路由，返回 APIRouter 或 None"""
        pass

    @abstractmethod
    def get_menus(self) -> List[Dict]:
        """注册菜单项"""
        pass

    def on_unload(self):
        """优雅关闭，最长等待 10 秒（由框架控制超时）"""
        pass
