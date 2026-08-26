"""
logger.py - 框架统一日志模块

功能：配置按天滚动的日志文件与控制台输出
支持 Web 界面临时调整日志级别
"""
import logging
import logging.handlers
import threading
from datetime import datetime
from pathlib import Path

from core.config_loader import LOG_DIR, get_core_config, get_user_config

_logger = None
_file_handler = None
_console_handler = None
_level_lock = threading.Lock()


def _get_logging_config() -> dict:
    """读取日志配置： 起 logging 段迁移至 user_config.yaml（可读写），
    此处优先读 user_config，缺失键回退 core.yaml（兼容旧实例迁移期）。
    server.debug 已删除——日志等级统一由 logging.level 控制，
    不再存在「debug 强制覆盖」逻辑。
    """
    user = get_user_config().get("logging") or {}
    core = get_core_config().get("logging") or {}
    merged = dict(core)
    merged.update({k: v for k, v in user.items() if v is not None})
    return merged


class DailySizeRotatingHandler(logging.Handler):
    """按天命名、超限滚动的日志处理器。

    文件名固定为 <log_dir>/YYYYMMDD-<prefix>.log（不使用 core.yaml 的 logging.file，
    该配置项仅用于说明日志所在目录）。跨天时自动切换到新文件；
    单文件超过 max_bytes 时按 .1/.2/... 后缀滚动，最多保留 backup_count 个。
    """

    def __init__(self, log_dir: Path, prefix: str, max_bytes: int, backup_count: int):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.prefix = prefix
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._current_path = None
        self._file = None
        self._lock = threading.Lock()

    def _path_for_today(self) -> Path:
        date = datetime.now().strftime("%Y%m%d")
        return self.log_dir / ("%s-%s.log" % (date, self.prefix))

    def emit(self, record):
        try:
            with self._lock:
                path = self._path_for_today()
                if self._current_path != path:
                    if self._file:
                        self._file.close()
                    self._current_path = path
                    self._file = open(path, "a", encoding="utf-8")
                msg = self.format(record)
                self._file.write(msg + "\n")
                self._file.flush()
                # 超过大小则滚动
                if path.stat().st_size > self.max_bytes:
                    self._rotate(path)
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def _rotate(self, path: Path):
        if self._file:
            self._file.close()
            self._file = None
        for index in range(self.backup_count - 1, 0, -1):
            old = path.with_suffix(path.suffix + ".%d" % index)
            new = path.with_suffix(path.suffix + ".%d" % (index + 1))
            if old.exists():
                old.replace(new)
        path.replace(path.with_suffix(path.suffix + ".1"))
        self._current_path = None

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
        super().close()


def _bind_uvicorn_loggers():
    """将 uvicorn 的日志器（uvicorn / uvicorn.error /
    uvicorn.access）共享到 netcore 的文件处理器与控制台处理器。

    此前 uvicorn 的 HTTP 访问日志（`[INFO] 10.x.x.x - "GET /api/... 200"`）走
    uvicorn 自身 logger，从未进入 netcore 日志文件——用户开启 DEBUG 后文件里仍
    没有请求记录，无法据日志排查。绑定后：
      - 文件：按当前级别写入（DEBUG 时含 access 日志）；
      - 控制台：与 netcore 同一 StreamHandler（跟随当前级别）。
    级别在 set_level() 时统一调整（见 set_level 内 _apply_level）。
    """
    global _file_handler
    try:
        import uvicorn  # noqa: F401
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            lg = logging.getLogger(name)
            lg.handlers.clear()
            lg.propagate = False
            if _file_handler is not None:
                lg.addHandler(_file_handler)
            lg.addHandler(_console_handler)
            lg.setLevel(getattr(logging, get_level(), logging.INFO))
    except Exception:  # noqa: BLE001
        pass


def setup_logger():
    """初始化框架日志器（按核心配置设置级别与滚动策略）"""
    global _logger, _file_handler, _console_handler
    logging_cfg = _get_logging_config()
    level_name = str(logging_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = logging_cfg.get("max_bytes", 10485760)
    backup_count = logging_cfg.get("backup_count", 30)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _logger = logging.getLogger("netcore")
    # 日志级别必须跟随配置 logging.level。
    _logger.setLevel(level)
    _logger.handlers.clear()
    _logger.propagate = False

    # 文件处理器：按天滚动
    _file_handler = DailySizeRotatingHandler(LOG_DIR, "netcore", max_bytes, backup_count)
    _file_handler.setLevel(level)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    _file_handler.setFormatter(fmt)
    _logger.addHandler(_file_handler)

    # 控制台处理器（跟随当前级别，不再固定 INFO）
    if _console_handler is None:
        _console_handler = logging.StreamHandler()
        _console_handler.setFormatter(fmt)
    else:
        _console_handler.setFormatter(fmt)
    _console_handler.setLevel(level)
    _logger.addHandler(_console_handler)

    # uvicorn 日志绑定到同一文件/控制台
    _bind_uvicorn_loggers()
    return _logger


def get_logger():
    """获取框架日志器"""
    global _logger
    if _logger is None:
        setup_logger()
    return _logger


def set_level(level_name: str):
    """动态设置日志级别（Web 界面调用），非法级别名返回 False。

    日志级别是啥，日志文件与控制台就存啥——
    同时调整「日志器 + 文件处理器 + 控制台处理器 + uvicorn 日志器」，
    DEBUG 时控制台同样输出请求/响应明细，方便直接复制控制台日志排查。
    """
    level = getattr(logging, str(level_name).upper(), None)
    if not isinstance(level, int):
        return False
    get_logger().setLevel(level)
    if _file_handler:
        _file_handler.setLevel(level)
    if _console_handler:
        _console_handler.setLevel(level)
    # uvicorn 三个 logger 同步级别
    try:
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            lg = logging.getLogger(name)
            lg.setLevel(level)
    except Exception:  # noqa: BLE001
        pass
    return True


def get_level() -> str:
    """返回当前日志级别名（Web 界面读取，用于前端 DEBUG 输出联动）。"""
    return logging.getLevelName(get_logger().level)
