from __future__ import annotations

import ast
import operator
from datetime import datetime, timezone

import httpx

from core.session.session import Session
from core.types import ToolCall, ToolResult

from .http_url_guard import HttpUrlGuardError, enforce_http_url_policy
from .network_policy import ToolNetworkPolicyConfig

# composition 将以此 ref 注册的工具替换为 make_http_get_handler(policy) 闭包
HTTP_GET_TOOL_REF = "modules.tools.builtin_handlers:http_get_tool"


def echo_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    return ToolResult(
        name=tool_call.name,
        output={
            "echo": dict(tool_call.arguments),
            "session_id": session.session_id,
        },
    )


def calc_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    expr = str(tool_call.arguments.get("expression", ""))
    value = _safe_eval(expr)
    return ToolResult(
        name=tool_call.name,
        output={
            "kind": "calc",
            "expression": expr,
            "value": value,
            "session_id": session.session_id,
        },
    )


def now_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    _ = tool_call
    now = datetime.now(timezone.utc)
    return ToolResult(
        name="now",
        output={
            "kind": "now",
            "iso_utc": now.isoformat(),
            "timestamp": now.timestamp(),
            "session_id": session.session_id,
        },
    )


def http_get_tool(session: Session, tool_call: ToolCall) -> ToolResult:
    """
    占位实现：生产路径须由 ``composition._build_tools`` 替换为 ``make_http_get_handler(policy)``。
    """
    _ = session
    return ToolResult(
        name=tool_call.name,
        output={
            "error": "http_get_unbound",
            "session_id": session.session_id,
        },
    )


def make_http_get_handler(policy: ToolNetworkPolicyConfig):
    """
    绑定 ``network_policy`` 的 GET 工具（不跟随重定向；响应体截断）。
    参数：``url``（必填），``timeout_seconds``（1–60，默认 10），``max_response_bytes``（1024–2_000_000，默认 256_000）。
    """

    def http_get_handler(session: Session, tool_call: ToolCall) -> ToolResult:
        raw = tool_call.arguments.get("url")
        if not isinstance(raw, str) or not raw.strip():
            return ToolResult(
                name=tool_call.name,
                output={
                    "error": "http_get_bad_url",
                    "session_id": session.session_id,
                },
            )
        url = raw.strip()
        try:
            enforce_http_url_policy(url, policy)
        except HttpUrlGuardError as e:
            return ToolResult(
                name=tool_call.name,
                output={
                    "error": "http_get_url_guard",
                    "reason": str(e),
                    "session_id": session.session_id,
                },
            )
        try:
            t = float(tool_call.arguments.get("timeout_seconds", 10.0))
        except (TypeError, ValueError):
            t = 10.0
        t = max(1.0, min(t, 60.0))
        try:
            mb = int(tool_call.arguments.get("max_response_bytes", 256_000))
        except (TypeError, ValueError):
            mb = 256_000
        mb = max(1024, min(mb, 2_000_000))
        preview_cap = 8192
        try:
            with httpx.Client(timeout=t, follow_redirects=False) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            return ToolResult(
                name=tool_call.name,
                output={
                    "error": "http_get_request_failed",
                    "detail": str(exc),
                    "session_id": session.session_id,
                },
            )
        ct_main = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        for pref in policy.http_blocked_content_type_prefixes:
            if pref and ct_main.startswith(pref):
                return ToolResult(
                    name=tool_call.name,
                    output={
                        "error": "http_get_content_type_blocked",
                        "content_type": ct_main,
                        "blocked_prefix": pref,
                        "session_id": session.session_id,
                    },
                )
        chunk = response.content[:mb]
        truncated = len(response.content) > len(chunk)
        text = chunk.decode("utf-8", errors="replace")
        preview = text[:preview_cap]
        ct = response.headers.get("content-type", "")
        return ToolResult(
            name=tool_call.name,
            output={
                "kind": "http_get",
                "url": url,
                "status_code": response.status_code,
                "content_type": ct,
                "body_preview": preview,
                "body_bytes": len(chunk),
                "preview_truncated": len(text) > len(preview),
                "body_truncated": truncated,
                "session_id": session.session_id,
            },
            source="http_fetch",
        )

    return http_get_handler


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(expr: str) -> float | int | None:
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    return _eval_node(node.body)


def _eval_node(node: ast.AST) -> float | int | None:
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return node.n  # type: ignore[no-any-return]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        operand = _eval_node(node.operand)
        if operand is None:
            return None
        return _OPS[type(node.op)](operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if left is None or right is None:
            return None
        return _OPS[type(node.op)](left, right)
    return None
