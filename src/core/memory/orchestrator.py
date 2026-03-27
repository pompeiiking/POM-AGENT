from __future__ import annotations

import json
import queue
import threading
import uuid
import httpx
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
from core.resource_access import RESOURCE_REMOTE_RETRIEVAL, ResourceAccessEvaluator


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
        resource_access: ResourceAccessEvaluator | None = None,
    ) -> None:
        self._store = store
        self._embedding = embedding
        self._policy = policy
        self._resource_access = resource_access
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

    # ── UserPreference CRUD ──

    def set_preference(self, user_id: str, key: str, value: str) -> str:
        """设置偏好（upsert 语义）：先 tombstone 同 key 旧行，再插入新行。返回新 memory_id。"""
        existing = self._store.get_preference_row(user_id, key)
        if existing is not None:
            self._store.tombstone_item(existing.memory_id)
        record = UserPreferenceRecord(user_id=user_id, key=key, value=value)
        return self.ingest_record(record)

    def get_preference(self, user_id: str, key: str) -> str | None:
        """读取偏好值；不存在返回 None。"""
        row = self._store.get_preference_row(user_id, key)
        if row is None:
            return None
        body = row.body_text
        sep = body.find("=")
        return body[sep + 1:] if sep >= 0 else body

    def list_preferences(self, user_id: str, *, limit: int = 100) -> list[tuple[str, str]]:
        """列举 (key, value) 对；按创建时间降序。"""
        rows = self._store.list_preference_rows(user_id, limit=limit)
        result: list[tuple[str, str]] = []
        for r in rows:
            body = r.body_text
            sep = body.find("=")
            if sep >= 0:
                result.append((body[:sep], body[sep + 1:]))
            else:
                result.append((body, ""))
        return result

    def delete_preference(self, user_id: str, key: str) -> bool:
        """删除偏好；返回是否实际删除了条目。"""
        row = self._store.get_preference_row(user_id, key)
        if row is None:
            return False
        self._store.tombstone_item(row.memory_id)
        return True

    # ── Fact CRUD ──

    def add_fact(self, user_id: str, statement: str, confidence: float = 1.0) -> str:
        """写入事实记录；返回 memory_id。"""
        record = FactRecord(user_id=user_id, statement=statement, confidence=confidence)
        return self.ingest_record(record)

    def get_fact(self, user_id: str, statement_prefix: str) -> str | None:
        """按 body_text 前缀查找事实；返回完整 statement 或 None。"""
        row = self._store.get_fact_row(user_id, statement_prefix)
        return row.body_text if row is not None else None

    def list_facts(self, user_id: str, *, limit: int = 100) -> list[str]:
        """列举事实 statement 列表；按创建时间降序。"""
        rows = self._store.list_fact_rows(user_id, limit=limit)
        return [r.body_text for r in rows]

    def delete_fact(self, user_id: str, statement_prefix: str) -> bool:
        """按 body_text 前缀 tombstone 事实；返回是否实际删除。"""
        row = self._store.get_fact_row(user_id, statement_prefix)
        if row is None:
            return False
        self._store.tombstone_item(row.memory_id)
        return True

    # ── 重索引与 tombstone 物理清理（嵌入模型变更 / 运维） ──

    def reindex_memory_id(self, memory_id: str) -> bool:
        """
        对单条非 tombstone 记录重建向量投影（先 pending 再同步或异步嵌入）。
        嵌入实现更换后应调用本方法或 `reindex_user_memories` 全量重算语义近邻。
        """
        row = self._store.get_row(memory_id)
        if row is None or row.tombstone != 0:
            return False
        self._store.set_embedding_status(memory_id, "pending")
        if self._policy.embedding_async:
            self._q.put(memory_id)
        else:
            self._embed_one_sync(memory_id=memory_id)
        return True

    def reindex_user_memories(self, user_id: str, *, limit: int = 500) -> int:
        """对某用户下最多 limit 条活跃记录依次重索引；返回成功调用 `reindex_memory_id` 的次数。"""
        ids = list(self._store.list_active_memory_ids_for_user(user_id, limit=limit))
        n = 0
        for mid in ids:
            if self.reindex_memory_id(mid):
                n += 1
        if self._policy.embedding_async:
            self.flush_embedding_queue()
        return n

    def purge_tombstoned_rows(self, *, limit: int = 10_000) -> int:
        """物理删除标准库中仍为 tombstone 的行（释放主表空间）；返回删除条数。"""
        return self._store.purge_tombstoned_rows(limit=limit)

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
        snippets: list[MemorySnippet] = []
        if any(xs for _n, xs in ranked_lists):
            fused = reciprocal_rank_fusion(ranked_lists, k=self._policy.rrf_k)
            fts_set = set(fts_ids_ordered)
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
        remote = self._retrieve_remote_snippets(user_id=user_id, channel=channel, query_text=q)
        if remote:
            seen = {s.memory_id for s in snippets}
            for r in remote:
                if r.memory_id not in seen:
                    snippets.append(r)
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

    def _retrieve_remote_snippets(self, *, user_id: str, channel: str | None, query_text: str) -> list[MemorySnippet]:
        url = str(getattr(self._policy, "remote_retrieval_url", "") or "").strip()
        if not url:
            return []
        gate = self._resource_access
        if gate is not None and not gate.is_allowed(RESOURCE_REMOTE_RETRIEVAL, "read"):
            return []
        if gate is not None and gate.requires_approval(RESOURCE_REMOTE_RETRIEVAL, "read"):
            return [
                MemorySnippet(
                    memory_id="policy:remote_retrieval_approval_required",
                    text="远端检索需要审批，当前已跳过 remote_retrieval 调用。",
                    score=0.0,
                    source="policy",
                )
            ]
        try:
            resp = httpx.post(
                url,
                json={
                    "user_id": user_id,
                    "channel": channel,
                    "query": query_text,
                    "top_k": int(self._policy.retrieve_top_k),
                },
                timeout=float(getattr(self._policy, "remote_timeout_seconds", 5.0)),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                return []
            out: list[MemorySnippet] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                mid = str(item.get("memory_id", "")).strip()
                txt = str(item.get("text", "")).strip()
                if not mid or not txt:
                    continue
                score_raw = item.get("score", 0.0)
                try:
                    score = float(score_raw)
                except Exception:
                    score = 0.0
                out.append(MemorySnippet(memory_id=mid, text=txt[:4000], score=score, source="remote"))
            return out[: self._policy.retrieve_top_k]
        except Exception:
            return []

