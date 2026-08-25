"""
core/timeutil.py - 统一时间基准工具

背景与规范
----------
框架约定：**所有落库的时间戳一律以 UTC 存储**（与 SQLite 的
``DEFAULT (datetime('now'))`` 保持一致，该函数返回的就是 UTC），
前端统一通过 ``window.NC.fmtTime()`` 按「系统设置 → 时区」换算成本地时间展示。

此前插件层大量使用 ``datetime.now``（本地时间）写库，与上述约定冲突，
导致两类可见错误：

* 任务管理「上次/下次执行」：库里存的是本地时间，前端又按 UTC 加 8 小时，
  显示时间比真实执行时间**快 8 小时**；
* 网络拓扑「快照时间」：库里存的是 UTC（SQLite 默认值），前端却原样展示，
  显示时间比真实时间**慢 8 小时**。

因此统一收敛到本模块：**入库用本模块的 UTC 函数，展示交给前端 fmtTime**。
日志文件（plugin.log / app.log）仍保留本地时间，便于人工直接阅读，
它们不入库、也不走 fmtTime。
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """当前 UTC 时间（naive，去掉 tzinfo，便于与库中既有格式一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_iso() -> str:
    """UTC ISO 字符串：2026-08-09T16:55:00.123456（供 last_run/started_at 等使用）。"""
    return utc_now().isoformat()


def utc_now_str() -> str:
    """UTC 常规字符串：2026-08-09 16:55:00（与 SQLite datetime('now') 同格式）。"""
    return utc_now().strftime("%Y-%m-%d %H:%M:%S")


def to_utc_str(dt: datetime) -> str:
    """把 datetime 转成 UTC 字符串。

    - 带时区的（如 APScheduler 返回的本地时区 aware 时间）按其时区换算成 UTC；
    - 不带时区的按**本机本地时间**解释后换算成 UTC。
    这样 Cron 仍按用户预期的本地时间触发，而落库值统一为 UTC。
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.astimezone()  # 附上本机时区
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
