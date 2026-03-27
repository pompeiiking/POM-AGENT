"""pytest 入口：确保 LogRecord 注入 request 上下文（不依赖 http_runtime 导入顺序）。"""
from __future__ import annotations

import infra.logging_config  # noqa: F401
