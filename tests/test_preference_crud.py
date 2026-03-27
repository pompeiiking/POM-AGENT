"""UserPreference CRUD：Orchestrator 层 + /preference 命令端到端测试。"""
from __future__ import annotations

import pytest

from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.user_intent import SystemPreference
from port.intent_parser import parse_user_intent
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore
from core.memory.embedding_hash import HashEmbeddingProvider


# ── helpers ──

def _policy() -> MemoryPolicyConfig:
    return MemoryPolicyConfig(
        enabled=True,
        retrieve_top_k=4,
        rrf_k=60,
        rerank_enabled=False,
        rerank_max_candidates=16,
        chunk_max_chars=256,
        chunk_overlap_chars=32,
        promote_on_archive=False,
        archive_chunk_max_chars=2000,
        archive_trust="medium",
        embedding_async=False,
        embedding_dim=16,
        fts_enabled=True,
        vector_max_candidates=200,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref="builtin:hash",
        embedding_openai=None,
    )


def _orchestrator() -> MemoryOrchestrator:
    store = SqliteDualMemoryStore(":memory:")
    emb = HashEmbeddingProvider(dim=16)
    return MemoryOrchestrator(store=store, embedding=emb, policy=_policy())


# ════════════════════════════════════════════════
# 1. Intent Parser: /preference 命令
# ════════════════════════════════════════════════

class TestPreferenceIntentParser:

    def test_set(self) -> None:
        intent = parse_user_intent("/preference set lang zh-CN")
        assert isinstance(intent, SystemPreference)
        assert intent.action == "set"
        assert intent.key == "lang"
        assert intent.value == "zh-CN"

    def test_set_value_with_spaces(self) -> None:
        intent = parse_user_intent("/preference set greeting hello world foo")
        assert isinstance(intent, SystemPreference)
        assert intent.action == "set"
        assert intent.key == "greeting"
        assert intent.value == "hello world foo"

    def test_get(self) -> None:
        intent = parse_user_intent("/preference get lang")
        assert isinstance(intent, SystemPreference)
        assert intent.action == "get"
        assert intent.key == "lang"

    def test_list(self) -> None:
        intent = parse_user_intent("/preference list")
        assert isinstance(intent, SystemPreference)
        assert intent.action == "list"

    def test_delete(self) -> None:
        intent = parse_user_intent("/preference delete lang")
        assert isinstance(intent, SystemPreference)
        assert intent.action == "delete"
        assert intent.key == "lang"

    def test_invalid_falls_through_to_chat(self) -> None:
        from core.user_intent import Chat
        intent = parse_user_intent("/preference")
        assert isinstance(intent, Chat)


# ════════════════════════════════════════════════
# 2. Orchestrator: Preference CRUD
# ════════════════════════════════════════════════

class TestPreferenceOrchestrator:

    def test_set_and_get(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "lang", "zh-CN")
        assert mo.get_preference("u1", "lang") == "zh-CN"

    def test_get_nonexistent(self) -> None:
        mo = _orchestrator()
        assert mo.get_preference("u1", "nope") is None

    def test_set_updates_existing(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "lang", "zh-CN")
        mo.set_preference("u1", "lang", "en-US")
        assert mo.get_preference("u1", "lang") == "en-US"

    def test_list_preferences(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "lang", "zh")
        mo.set_preference("u1", "theme", "dark")
        prefs = mo.list_preferences("u1")
        keys = {k for k, v in prefs}
        assert keys == {"lang", "theme"}

    def test_list_empty(self) -> None:
        mo = _orchestrator()
        assert mo.list_preferences("u1") == []

    def test_delete(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "lang", "zh")
        assert mo.delete_preference("u1", "lang") is True
        assert mo.get_preference("u1", "lang") is None

    def test_delete_nonexistent(self) -> None:
        mo = _orchestrator()
        assert mo.delete_preference("u1", "nope") is False

    def test_user_isolation(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "lang", "zh")
        mo.set_preference("u2", "lang", "en")
        assert mo.get_preference("u1", "lang") == "zh"
        assert mo.get_preference("u2", "lang") == "en"

    def test_value_with_equals_sign(self) -> None:
        mo = _orchestrator()
        mo.set_preference("u1", "formula", "a=b+c")
        assert mo.get_preference("u1", "formula") == "a=b+c"
