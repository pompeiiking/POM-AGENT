"""request 上下文与日志注入（Phase 4.1）。"""
from __future__ import annotations

import logging

from infra.request_context import bind_request_context, get_channel, get_request_id, get_user_id, reset_request_context


def test_context_bind_and_reset() -> None:
    assert get_request_id() is None
    tok = bind_request_context(request_id="rid-1", user_id="u1", channel="c1")
    try:
        assert get_request_id() == "rid-1"
        assert get_user_id() == "u1"
        assert get_channel() == "c1"
    finally:
        reset_request_context(tok)
    assert get_request_id() is None


def test_logrecord_has_request_fields() -> None:
    factory = logging.getLogRecordFactory()
    tok = bind_request_context(request_id="req-x", user_id="ux", channel="cx")
    try:
        record = factory("test_req", logging.INFO, __file__, 1, "hello", (), None)
        assert record.request_id == "req-x"
        assert record.user_id == "ux"
        assert record.channel == "cx"
    finally:
        reset_request_context(tok)
