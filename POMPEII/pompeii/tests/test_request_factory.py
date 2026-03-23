from __future__ import annotations

from port.input_events import UserMessageInput
from port.request_factory import http_request_factory, session_request_factory


def test_session_request_factory_unique_request_id_per_message() -> None:
    rf = session_request_factory(user_id="u", channel="http")
    a = rf(UserMessageInput(kind="user_message", text="hi"))
    b = rf(UserMessageInput(kind="user_message", text="hi"))
    assert a.request_id != b.request_id
    assert a.user_id == "u" and a.channel == "http"
    assert b.user_id == "u" and b.channel == "http"


def test_http_request_factory_defaults() -> None:
    rf = http_request_factory()
    r = rf(UserMessageInput(kind="user_message", text="x"))
    assert r.user_id == "http-user"
    assert r.channel == "http"
    assert len(r.request_id) >= 32
