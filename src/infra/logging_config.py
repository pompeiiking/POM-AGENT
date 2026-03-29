"""
结构化日志：在创建 ``LogRecord`` 时注入 ``request_id`` / ``user_id`` / ``channel``（来自 ``request_context``），
使任意 logger 的 Formatter 可使用 ``%(request_id)s`` 等字段。

模块导入时安装 ``LogRecord`` 工厂（链式包装已有工厂）。进程入口可再调用 ``setup_structured_logging()`` 配置 stderr handler。
"""
from __future__ import annotations

import logging
from typing import Any

from infra.request_context import get_channel, get_request_id, get_user_id

_INSTALLED = False


def _inject_context_attrs(record: logging.LogRecord) -> logging.LogRecord:
    rid = get_request_id()
    record.request_id = rid if rid is not None else "-"
    uid = get_user_id()
    record.user_id = uid if uid is not None else "-"
    ch = get_channel()
    record.channel = ch if ch is not None else "-"
    return record


def _chain_record_factory() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        return _inject_context_attrs(record)

    logging.setLogRecordFactory(record_factory)
    _INSTALLED = True


_chain_record_factory()


def setup_structured_logging(*, level: int = logging.INFO) -> None:
    """
    若 root 尚无 handler，则配置 stderr + 单行文本格式（含 request 上下文字段）。
    ``LogRecord`` 注入已在模块导入时完成。
    """
    root = logging.getLogger()
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s "
                "user_id=%(user_id)s channel=%(channel)s %(message)s"
            )
        )
        root.addHandler(h)
    root.setLevel(level)
