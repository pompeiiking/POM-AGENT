from __future__ import annotations

import pytest

from infra.model_http_client_pool import clear_model_http_client_pool, get_pooled_httpx_client


@pytest.fixture(autouse=True)
def _clear_pool() -> None:
    clear_model_http_client_pool()
    yield
    clear_model_http_client_pool()


def test_pool_returns_same_client_for_same_key() -> None:
    a = get_pooled_httpx_client(base_url="https://api.example.com", timeout=30.0)
    b = get_pooled_httpx_client(base_url="https://api.example.com", timeout=30.0)
    assert a is b


def test_pool_different_timeout_is_different_client() -> None:
    a = get_pooled_httpx_client(base_url="https://api.example.com", timeout=30.0)
    b = get_pooled_httpx_client(base_url="https://api.example.com", timeout=60.0)
    assert a is not b


def test_pool_different_host_is_different_client() -> None:
    a = get_pooled_httpx_client(base_url="https://a.com", timeout=10.0)
    b = get_pooled_httpx_client(base_url="https://b.com", timeout=10.0)
    assert a is not b
