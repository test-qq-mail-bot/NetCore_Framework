"""
audit.py - 统一审计日志接口

功能：向插件与框架提供线程安全的审计日志写入函数 audit_log
自动填充时间戳(UTC)、IP、用户名

存储格式：JSONL（每行一条独立 JSON），按天切分为
    data/logs/audit/audit-YYYYMMDD.log
选用 JSONL 而非单个 JSON 数组，是为了支持「只追加写入」——
崩溃或断电最多损坏最后一行，不会破坏整份文件，也便于外部工具逐行流式处理。
"""
import json
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from core.config_loader import AUDIT_DIR

# 请求上下文：当前用户名与客户端 IP（由认证中间件设置）
ctx_username = ContextVar("ctx_username", default=None)
ctx_client_ip = ContextVar("ctx_client_ip", default=None)

# 写入锁，保证多线程下 JSONL 不交错
_audit_lock = threading.Lock()


def audit_log(action: str, detail: str = "", result: str = "success", username: str = None):
    """
    写入一条审计日志记录。

    参数:
        action:   操作类型，如 "device_backup"、"config_change"、"notify_test" 等。
        detail:   操作详情，可包含设备 IP、配置差异摘要等自由文本。
        result:   操作结果，可选 "success" 或 "failed"。
        username: 操作人，默认 None。若为 None 且当前存在 HTTP 请求上下文，
                  则自动提取已认证用户名；否则使用 "system"。
    """
    ip = ctx_client_ip.get()
    if ip is None:
        ip = "127.0.0.1"
    if username is None:
        username = ctx_username.get() or "system"

    now = datetime.now(timezone.utc)
    record = {
        # 统一 UTC + 毫秒精度：strftime 不支持毫秒，故用 microsecond//1000 手工补 3 位
        "timestamp_utc": now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000),
        "ip": ip,
        "username": username,
        "action": action,
        "result": result,
        "detail": detail,
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y%m%d")
    path = AUDIT_DIR / ("audit-%s.log" % date_str)
    line = json.dumps(record, ensure_ascii=False)
    # 先序列化再进锁，缩短临界区；锁保证多线程下整行原子追加、不互相交错
    with _audit_lock:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return record


def query_audit(page: int = 1, size: int = 50, ip: str = None, result: str = None,
                action: str = None, start_date: str = None, end_date: str = None,
                sort_by: str = "timestamp_utc", sort_order: str = "desc",
                filter_col: str = None, filter_values: list = None):
    """
    分页查询审计日志。
    返回 (records, total)

    实现要点与已知约束（调用方务必了解）：
    - 文件按日期倒序遍历（新日期在前），单个文件内是写入时的正序；
      读取完成后对全部命中记录做一次整体反转，保证返回结果严格按时间
      从新到旧（最新操作在最前），不再出现「天内正序导致当天最新操作沉底」；
    - 过滤与分页都在内存中完成：先把命中过滤条件的记录全部读入 all_records
      得到准确的 total，再按 page/size 切片。日志量极大时开销与内存占用较高，
      因此导出接口（api.audit_export）必须限制单次条数上限。
    """
    _FILTER_KEYS = ("timestamp_utc", "ip", "action", "result", "detail", "username")
    files = sorted(AUDIT_DIR.glob("audit-*.log"), reverse=True)
    # 按日期范围过滤文件：文件名中的 YYYYMMDD 与 start/end_date 同为定长字符串，
    # 可直接做字典序比较，等价于日期比较，省去解析开销
    selected = []
    for f in files:
        stem = f.stem.replace("audit-", "")
        if start_date and stem < start_date:
            continue
        if end_date and stem > end_date:
            continue
        selected.append(f)

    all_records = []
    for f in selected:
        with open(f, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    # 跳过损坏行（例如断电导致最后一行写了一半），不影响其余记录
                    continue
                if ip and rec.get("ip") != ip:
                    continue
                if result and rec.get("result") != result:
                    continue
                if action and rec.get("action") != action:
                    continue
                if filter_col in _FILTER_KEYS and filter_values:
                    _rv = rec.get(filter_col)
                    if _rv is None:
                        _rv = ""
                    if _rv not in filter_values:
                        continue
                all_records.append(rec)

    # 反转到新日期之前，导致「最新日志不是第一页第一条」的乱序。
    _SORT_KEYS = ("timestamp_utc", "ip", "action", "result", "detail", "username")
    sb = sort_by if sort_by in _SORT_KEYS else "timestamp_utc"
    reverse = (sort_order or "").lower() != "asc"
    try:
        all_records.sort(key=lambda r: str(r.get(sb) or ""), reverse=reverse)
    except Exception:  # noqa: BLE001
        if reverse:
            all_records.reverse()
    total = len(all_records)
    start = (page - 1) * size
    end = start + size
    return all_records[start:end], total


def clean_audit():
    """清理**全部**审计日志文件（尽力而为，删除被拦截时不报错）。

    注意：这里是一次性清空，不区分日期；core.yaml 的
    logging.audit_log_retention_days 目前只是预留配置，并未在此生效。
    返回实际删除成功的文件数。
    """
    count = 0
    for f in AUDIT_DIR.glob("audit-*.log"):
        try:
            f.unlink()
            count += 1  # 仅删除成功才计数，避免返回虚假的清理数量
        except OSError:
            # 删除被环境（如安全删除机制）拦截时，跳过该文件，不阻断清理流程
            pass
    return count
