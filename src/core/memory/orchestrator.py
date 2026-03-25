from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from .chunking import chunk_text
from .policy_config import MemoryPolicyConfig
from .content import (
    ArchiveLinkRecord,
    FactRecord,
    LongTermMemoryRecord,
    MemoryChunkRecord,
    TrustLevel,
    UserPreferenceRecord,
)
from .fts_query import build_fts_match_query
from .ports import DualMemoryStore, EmbeddingProvider
from .rerank_lexical import lexical_rerank
from .rrf import reciprocal_rank_fusion
from .snippets import MemorySnippet
from core.session.session import Session
from core.session.session_archive import build_archive_row_dict, build_dialogue_plain_for_archive


def _record_meta(record: LongTermMemoryRecord) -> dict[str, Any]:
    d = asdict(record)
    return {k: v for k, v in d.items()}


class MemoryOrchestrator:
    """
    长期域编排：先标准库后向量投影；检索融合 FTS + 向量 + 可选 lexical rerank。
    """

    def __init__(
        self,
        store: DualMemoryStore,
        embedding: EmbeddingProvider,
        policy: MemoryPolicyConfig,
    ) -> None:
        self._store = store
        self._embedding = embedding
        self._policy = policy
        self._q: queue.Queue[str] = queue.Queue()
        self._worker_started = False
        if policy.embedding_async:
            self._start_worker()

    def _start_worker(self) -> None:
        if self._worker_started:
            return
        self._worker_started = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self) -> None:
        while True:
            mid = self._q.get()
            try:
                self._embed_one_sync(memory_id=mid)
            except Exception:
                self._store.set_embedding_status(mid, "failed")

    @property
    def policy(self) -> MemoryPolicyConfig:
        return self._policy

    def close(self) -> None:
        self._store.close()

    def _json_default(self, obj: object) -> object:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError

    def ingest_record(self, record: LongTermMemoryRecord) -> str:
        memory_id = uuid.uuid4().hex
        channel, body_text, trust, source_session_id = self._extract_fields(record)
        meta = _record_meta(record)
        meta_json = json.dumps(meta, ensure_ascii=False, default=self._json_default)
        self._store.insert_item(
            memory_id=memory_id,
            kind=record.kind,
            user_id=record.user_id,
            channel=channel,
            body_text=body_text,
            trust=trust,
            embedding_status="pending",
            source_session_id=source_session_id,
            meta_json=meta_json,
        )
        self._store.sync_fts_for_memory_id(memory_id)
        if self._policy.embedding_async:
            self._q.put(memory_id)
        else:
            self._embed_one_sync(memory_id=memory_id)
        return memory_id

    def _extract_fields(self, record: LongTermMemoryRecord) -> tuple[str | None, str, str, str | None]:
        if isinstance(record, MemoryChunkRecord):
            return record.channel, record.text, record.trust, record.source_session_id
        if isinstance(record, UserPreferenceRecord):
            body = f"{record.key}={record.value}"
            return None, body, "high", None
        if isinstance(record, FactRecord):
            return None, record.statement, "medium", None
        if isinstance(record, ArchiveLinkRecord):
            body = f"{record.summary_excerpt}\n{record.session_id}"
            return None, body, "medium", record.session_id
        raise TypeError(type(record))

    def _embed_one_sync(self, *, memory_id: str) -> None:
        row = self._store.get_row(memory_id)
        if row is None or row.tombstone != 0:
            return
        self._store.clear_memory(memory_id)
        chunks = chunk_text(
            row.body_text,
            max_chars=self._policy.chunk_max_chars,
            overlap_chars=self._policy.chunk_overlap_chars,
        )
        for i, ch in enumerate(chunks):
            if not ch.strip():
                continue
            cid = f"{memory_id}:{i}"
            vec = self._embedding.embed(ch)
            self._store.insert_chunk(
                chunk_id=cid,
                memory_id=memory_id,
                user_id=row.user_id,
                chunk_text=ch,
                vector=vec,
            )
        self._store.set_embedding_status(memory_id, "ready")

    def promote_archived_session(self, session: Session) -> None:
        if not self._policy.promote_on_archive:
            return
        body = build_dialogue_plain_for_archive(session, max_chars=self._policy.archive_chunk_max_chars)
        row = build_archive_row_dict(session)
        excerpt = str(row.get("summary_text", ""))[:500]
        ar = self._policy.archive_trust.strip().lower()
        trust_level: TrustLevel = cast(
            TrustLevel,
            ar if ar in ("low", "medium", "high") else "medium",
        )
        text = body if body.strip() else excerpt
        if not text.strip():
            return
        chunk = MemoryChunkRecord(
            user_id=session.user_id,
            text=text,
            channel=session.channel,
            source_session_id=session.session_id,
            trust=trust_level,
        )
        self.ingest_record(chunk)
        link = ArchiveLinkRecord(
            user_id=session.user_id,
            session_id=session.session_id,
            summary_excerpt=excerpt,
        )
        self.ingest_record(link)

    def forget_phrase(self, user_id: str, phrase: str) -> int:
        return self._store.tombstone_by_phrase(user_id, phrase, limit=20)

    def retrieve_for_context(self, *, user_id: str, channel: str | None, query_text: str) -> list[MemorySnippet]:
        if not self._policy.enabled:
            return []
        q = query_text.strip()
        if not q:
            return []
        ranked_lists: list[tuple[str, list[str]]] = []
        fts_ids_ordered: list[str] = []
        if self._policy.fts_enabled:
            fq = build_fts_match_query(q)
            if fq is not None:
                fts_hits = self._store.fts_search(user_id, fq, limit=40)
                fts_ids_ordered = [mid for mid, _ in fts_hits]
                ranked_lists.append(("fts", fts_ids_ordered))
        qvec = self._embedding.embed(q)
        vec_hits = self._store.search_cosine(
            user_id=user_id,
            query_vec=qvec,
            limit=40,
            max_scan=self._policy.vector_max_candidates,
        )
        vec_mids = []
        seen: set[str] = set()
        for _cid, mid, _s in vec_hits:
            if mid not in seen:
                seen.add(mid)
                vec_mids.append(mid)
        ranked_lists.append(("vec", vec_mids))
        if not any(xs for _n, xs in ranked_lists):
            return []
        fused = reciprocal_rank_fusion(ranked_lists, k=self._policy.rrf_k)
        fts_set = set(fts_ids_ordered)
        snippets: list[MemorySnippet] = []
        for mid, rrf_score in fused:
            if len(snippets) >= self._policy.rerank_max_candidates:
                break
            row = self._store.get_row(mid)
            if row is None or row.tombstone != 0:
                continue
            if not self._store.row_matches_channel(row, channel, policy=self._policy.channel_filter):
                continue
            if row.embedding_status == "pending" and mid not in fts_set:
                continue
            snippets.append(
                MemorySnippet(
                    memory_id=mid,
                    text=row.body_text[:4000],
                    score=float(rrf_score),
                    source="rrf",
                )
            )
        if self._policy.rerank_enabled and snippets:
            snippets = lexical_rerank(q, snippets, max_output=self._policy.retrieve_top_k)
        else:
            snippets = snippets[: self._policy.retrieve_top_k]
        return snippets

    def retrieve_as_tool_json(self, *, user_id: str, channel: str | None, query_text: str) -> list[dict[str, Any]]:
        return [
            {"memory_id": s.memory_id, "text": s.text, "score": s.score}
            for s in self.retrieve_for_context(user_id=user_id, channel=channel, query_text=query_text)
        ]

    def flush_embedding_queue(self) -> None:
        """测试与同步场景：排空异步嵌入队列（与后台线程存在竞态时多调一次）。"""
        if self._policy.embedding_async:
            try:
                while True:
                    mid = self._q.get_nowait()
                    self._embed_one_sync(memory_id=mid)
            except queue.Empty:
                pass

