from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from core.session.session import (
    Message,
    Part,
    Session,
    SessionConfig,
    SessionLimits,
    SessionStats,
    SessionStatus,
)


def session_to_json_dict(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "channel": session.channel,
        "config": _config_to_dict(session.config),
        "status": session.status.value,
        "stats": _stats_to_dict(session.stats),
        "messages": [_message_to_dict(m) for m in session.messages],
    }


def session_from_json_dict(data: dict[str, Any]) -> Session:
    return Session(
        session_id=str(data["session_id"]),
        user_id=str(data["user_id"]),
        channel=str(data["channel"]),
        config=_config_from_dict(data["config"]),
        status=SessionStatus(str(data["status"])),
        stats=_stats_from_dict(data["stats"]),
        messages=[_message_from_dict(m) for m in data.get("messages", [])],
    )


def _config_to_dict(c: SessionConfig) -> dict[str, Any]:
    return {
        "model": c.model,
        "skills": list(c.skills),
        "security": c.security,
        "prompt_profile": c.prompt_profile,
        "prompt_strategy": c.prompt_strategy,
        "limits": {
            "max_tokens": c.limits.max_tokens,
            "max_context_window": c.limits.max_context_window,
            "max_loops": c.limits.max_loops,
            "timeout_seconds": c.limits.timeout_seconds,
            "assembly_tail_messages": c.limits.assembly_tail_messages,
            "summary_tail_messages": c.limits.summary_tail_messages,
            "summary_excerpt_chars": c.limits.summary_excerpt_chars,
            "assembly_message_max_chars": c.limits.assembly_message_max_chars,
            "assembly_approx_context_tokens": c.limits.assembly_approx_context_tokens,
            "assembly_compress_tool_max_chars": c.limits.assembly_compress_tool_max_chars,
            "assembly_compress_early_turn_chars": c.limits.assembly_compress_early_turn_chars,
            "assembly_token_counter": c.limits.assembly_token_counter,
            "assembly_tiktoken_encoding": c.limits.assembly_tiktoken_encoding,
        },
    }


def _config_from_dict(d: dict[str, Any]) -> SessionConfig:
    lim = d["limits"]
    return SessionConfig(
        model=str(d["model"]),
        skills=list(d["skills"]),
        security=d["security"],
        prompt_profile=str(d.get("prompt_profile", "default")),
        prompt_strategy=str(d.get("prompt_strategy", "default")),
        limits=SessionLimits(
            max_tokens=int(lim["max_tokens"]),
            max_context_window=int(lim["max_context_window"]),
            max_loops=int(lim["max_loops"]),
            timeout_seconds=float(lim["timeout_seconds"]),
            assembly_tail_messages=int(lim.get("assembly_tail_messages", 20)),
            summary_tail_messages=int(lim.get("summary_tail_messages", 12)),
            summary_excerpt_chars=int(lim.get("summary_excerpt_chars", 200)),
            assembly_message_max_chars=int(lim.get("assembly_message_max_chars", 0)),
            assembly_approx_context_tokens=int(lim.get("assembly_approx_context_tokens", 0)),
            assembly_compress_tool_max_chars=int(lim.get("assembly_compress_tool_max_chars", 0)),
            assembly_compress_early_turn_chars=int(lim.get("assembly_compress_early_turn_chars", 0)),
            assembly_token_counter=_lim_token_counter(lim),
            assembly_tiktoken_encoding=str(lim.get("assembly_tiktoken_encoding", "cl100k_base")),
        ),
    )


def _lim_token_counter(lim: dict[str, Any]) -> str:
    raw = lim.get("assembly_token_counter", "heuristic")
    if not isinstance(raw, str):
        return "heuristic"
    v = raw.strip().lower()
    return v if v in ("heuristic", "tiktoken") else "heuristic"


def _stats_to_dict(s: SessionStats) -> dict[str, Any]:
    return {
        "total_tokens_used": s.total_tokens_used,
        "message_count": s.message_count,
        "created_at": s.created_at.isoformat(),
        "last_active_at": s.last_active_at.isoformat(),
    }


def _stats_from_dict(d: dict[str, Any]) -> SessionStats:
    return SessionStats(
        total_tokens_used=int(d["total_tokens_used"]),
        message_count=int(d["message_count"]),
        created_at=datetime.fromisoformat(str(d["created_at"])),
        last_active_at=datetime.fromisoformat(str(d["last_active_at"])),
    )


def _message_to_dict(m: Message) -> dict[str, Any]:
    return {
        "message_id": m.message_id,
        "role": m.role,
        "parts": [_part_to_dict(p) for p in m.parts],
        "timestamp": m.timestamp.isoformat(),
        "loop_index": m.loop_index,
        "token_count": m.token_count,
    }


def _message_from_dict(d: dict[str, Any]) -> Message:
    return Message(
        message_id=str(d["message_id"]),
        role=str(d["role"]),
        parts=[_part_from_dict(p) for p in d["parts"]],
        timestamp=datetime.fromisoformat(str(d["timestamp"])),
        loop_index=int(d["loop_index"]),
        token_count=int(d["token_count"]),
    )


def _part_to_dict(p: Part) -> dict[str, Any]:
    c: Any
    if isinstance(p.content, bytes):
        c = {"__bytes_b64__": base64.b64encode(p.content).decode("ascii")}
    else:
        c = p.content
    return {"type": p.type, "content": c, "metadata": dict(p.metadata)}


def _part_from_dict(d: dict[str, Any]) -> Part:
    raw = d["content"]
    if isinstance(raw, dict) and "__bytes_b64__" in raw:
        content: str | dict | bytes = base64.b64decode(str(raw["__bytes_b64__"]))
    else:
        content = raw
    return Part(type=str(d["type"]), content=content, metadata=dict(d.get("metadata") or {}))
