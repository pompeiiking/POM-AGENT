from __future__ import annotations

import pytest

from modules.model.config import ModelProvider
from modules.model.openai_provider_route import (
    build_openai_chat_route,
    chat_completions_url,
    clear_openai_chat_route_cache,
    get_openai_chat_route,
)


@pytest.fixture(autouse=True)
def _clear_route_cache() -> None:
    clear_openai_chat_route_cache()
    yield
    clear_openai_chat_route_cache()


def test_model_overrides_model_id() -> None:
    p = ModelProvider(
        id="t1",
        backend="openai_compatible",
        params={
            "api_key_env": "K",
            "base_url": "https://example.com",
            "model_id": "deepseek/deepseek-chat",
            "model": "override-model",
        },
    )
    r = build_openai_chat_route(p)
    assert r.ok and r.route is not None
    assert r.route.model == "override-model"
    assert r.route.base_url == "https://example.com"


def test_model_id_infers_deepseek_base() -> None:
    p = ModelProvider(
        id="t2",
        backend="openai_compatible",
        params={"api_key_env": "K", "model_id": "deepseek/deepseek-chat"},
    )
    r = build_openai_chat_route(p)
    assert r.ok and r.route is not None
    assert r.route.base_url == "https://api.deepseek.com"
    assert r.route.model == "deepseek-chat"
    assert chat_completions_url(r.route) == "https://api.deepseek.com/v1/chat/completions"


def test_unknown_vendor_requires_base_url() -> None:
    p = ModelProvider(
        id="t3",
        backend="openai_compatible",
        params={"api_key_env": "K", "model_id": "unknownvendor/foo"},
    )
    r = build_openai_chat_route(p)
    assert not r.ok
    assert r.error_message and "unknownvendor" in r.error_message


def test_cache_same_provider_twice() -> None:
    p = ModelProvider(
        id="cache_id",
        backend="openai_compatible",
        params={"api_key_env": "K", "base_url": "https://x.test", "model": "m"},
    )
    a = get_openai_chat_route(p)
    b = get_openai_chat_route(p)
    assert a.route is b.route


def test_missing_api_key_env() -> None:
    p = ModelProvider(id="t4", backend="openai_compatible", params={"base_url": "https://a.com"})
    r = build_openai_chat_route(p)
    assert not r.ok and r.error_message and "api_key_env" in r.error_message
