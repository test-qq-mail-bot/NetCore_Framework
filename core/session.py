"""
session.py - 会话超时管理模块

功能：基于「空闲时长」的会话超时控制。

生命周期：
  1. 登录成功后 api.auth_login 调用 create() 登记 token；
  2. 之后每个受保护接口都会经过 auth.get_current_user，由它调用 touch()
     判定是否超时并顺带续期（前端心跳 /api/auth/heartbeat 也走这条路径）；
     ——注意续期主要靠 touch()，reset() 只是给 /api/system/session/reset 用的显式重置；
  3. 空闲超过 user_config.yaml 的 system.auto_logout_minutes 即判定失效并移除；
  4. 注销时 remove() 删除登记。

会话表仅存于内存：进程重启后所有 token 都会被 touch() 判为「未登记」而要求重新登录。
"""
import threading
import time

from core.config_loader import get_user_config
from core.logger import get_logger

logger = get_logger()


class SessionManager:
    """会话管理器（单例），维护 token -> 最后活跃时间"""

    def __init__(self):
        self._sessions = {}  # token -> last_activity 时间戳
        self._lock = threading.Lock()

    def _idle_timeout(self) -> int:
        # 读取基础设置中的「自动退出时间（分钟）」；0 表示关闭自动退出。
        # 每次调用都重新读配置（get_user_config 带缓存），保证界面上改完立即生效。
        try:
            return int(get_user_config().get("system", {}).get("auto_logout_minutes", 5) or 5)
        except (TypeError, ValueError):
            return 5

    def touch(self, token: str) -> bool:
        """刷新会话活跃时间（续期）。

        返回 True 表示会话已失效（调用方应拒绝并强制退出），
        返回 False 表示有效并已续期。
        会话未登记（已登出 / 已超时移除 / 后端重启后）视为失效，要求重新登录。
        """
        idle = self._idle_timeout()
        with self._lock:
            last = self._sessions.get(token)
            if last is None:
                # 未登记：已登出或已超时，拒绝续期
                return True
            if idle <= 0:
                return False
            if (time.time() - last) > idle * 60:
                self._sessions.pop(token, None)
                return True
            self._sessions[token] = time.time()
            return False

    def create(self, token: str):
        """登录成功后登记会话（未登记的 token 一律被 touch 判为失效）"""
        with self._lock:
            self._sessions[token] = time.time()

    def reset(self, token: str) -> bool:
        """重置会话活跃时间，返回是否存在该会话"""
        with self._lock:
            if token in self._sessions:
                self._sessions[token] = time.time()
                return True
        return False

    def remaining(self, token: str) -> int:
        """返回剩余空闲秒数；-1 表示已关闭自动退出"""
        idle = self._idle_timeout()
        if idle <= 0:
            return -1  # 永不超时
        with self._lock:
            last = self._sessions.get(token)
        if last is None:
            # 未登记（已登出/已超时）：此处只做展示用，返回完整时长，
            # 真正的拦截由 touch() 在 get_current_user 中完成
            return idle * 60
        remain = int(idle * 60 - (time.time() - last))
        return max(0, remain)

    def remove(self, token: str):
        """注销时删除会话登记"""
        with self._lock:
            self._sessions.pop(token, None)


_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return _session_manager
