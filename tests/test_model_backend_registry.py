from __future__ import annotations

import pytest

from modules.model.model_backend_registry import ModelBackendRegistryError, resolve_model_chat_backend


def test_resolve_builtin_openai_chat_returns_callable() -> None:
    fn = resolve_model_chat_backend("builtin:openai_chat")
    assert callable(fn)


def test_resolve_unknown_ref_raises() -> None:
    with pytest.raises(ModelBackendRegistryError):
        resolve_model_chat_backend("vendor:anthropic_native")
