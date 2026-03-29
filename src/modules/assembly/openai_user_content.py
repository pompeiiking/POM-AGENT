"""
组装部 → 模型部（OpenAI Chat）user 消息的 content 形态统一出口。

对应架构 ver0.4 §3.1「Context Window 内容块」在 **user 轮** 上落到 OpenAI 兼容 API 的桥梁；
``apply_user_parts_preprocessing`` 执行关卡⑤（``multimodal_image_url``）与基线 URL 校验，
并在 ``tools.network_policy.http_url_guard_enabled`` 时复用 ``http_url_guard`` 白名单逻辑。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import ParseResult, urlparse

from core.resource_access import RESOURCE_MULTIMODAL_IMAGE_URL
from core.session.multimodal_user_payload import message_to_openai_user_blocks
from core.session.rule_summary import render_message_plain_text
from core.session.session import Message, Part
from modules.tools.http_url_guard import (
    HttpUrlGuardError,
    assert_safe_http_tool_url,
    multimodal_image_url_host_baseline_violation,
)


def _baseline_http_image_url_parsed(parsed: ParseResult) -> str | None:
    """解析后的 URL：仅 http(s)、禁 userinfo、须有 host。返回错误码或 ``None``。"""
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return "bad_scheme"
    if parsed.username is not None or parsed.password is not None:
        return "userinfo_forbidden"
    if not parsed.hostname:
        return "missing_host"
    return None


def apply_user_parts_preprocessing(
    parts: Sequence[Part],
    *,
    session_meta: Mapping[str, Any] | None = None,
) -> list[Part]:
    """
    用户多模态/多段 Part 在进入 OpenAI 载荷前的钩子：

    - 关卡⑤：``multimodal_image_url`` read deny 时以文本占位替换 ``image_url`` Part。
    - 基线：非 http(s) / userinfo / 无 host；**localhost** 与**高风险字面 IP**（私网/环回等，同 ``http_url_guard``）丢弃。
    - 若 ``session_meta.multimodal_http_url_guard_enabled``：按 ``http_url_guard`` + ``allowed_hosts`` 校验。
    """
    meta = session_meta or {}
    resource_ok = bool(meta.get("multimodal_image_url_read_allowed", True))
    guard_on = bool(meta.get("multimodal_http_url_guard_enabled", False))
    hosts_raw = meta.get("multimodal_http_url_allowed_hosts")
    if isinstance(hosts_raw, (list, tuple)):
        hosts: tuple[str, ...] = tuple(str(h).strip() for h in hosts_raw if str(h).strip())
    else:
        hosts = ()

    out: list[Part] = []
    for p in parts:
        if p.type != "image_url":
            out.append(p)
            continue
        if not resource_ok:
            out.append(
                Part(
                    type="text",
                    content="[image omitted: multimodal_image_url denied by resource_access]",
                    metadata={"omitted": RESOURCE_MULTIMODAL_IMAGE_URL},
                )
            )
            continue
        c = p.content
        if not isinstance(c, dict):
            out.append(
                Part(
                    type="text",
                    content="[image omitted: invalid image_url part]",
                    metadata={"omitted": "bad_part"},
                )
            )
            continue
        url = c.get("url")
        raw_u = url.strip() if isinstance(url, str) else ""
        if not raw_u:
            out.append(
                Part(
                    type="text",
                    content="[image omitted: empty_url]",
                    metadata={"omitted": "baseline_url", "reason": "empty_url"},
                )
            )
            continue
        parsed = urlparse(raw_u)
        bl = _baseline_http_image_url_parsed(parsed)
        if bl is not None:
            out.append(
                Part(
                    type="text",
                    content=f"[image omitted: {bl}]",
                    metadata={"omitted": "baseline_url", "reason": bl},
                )
            )
            continue
        host_bad = multimodal_image_url_host_baseline_violation(parsed.hostname)
        if host_bad is not None:
            out.append(
                Part(
                    type="text",
                    content=f"[image omitted: {host_bad}]",
                    metadata={"omitted": "baseline_host", "reason": host_bad},
                )
            )
            continue
        if guard_on:
            try:
                assert_safe_http_tool_url(raw_u, allowed_hosts=hosts)
            except HttpUrlGuardError as exc:
                out.append(
                    Part(
                        type="text",
                        content=f"[image omitted: url guard ({exc})]",
                        metadata={"omitted": "http_url_guard"},
                    )
                )
                continue
        out.append(p)
    return out


def openai_user_message_payload(
    message: Message,
    *,
    session_meta: Mapping[str, Any] | None = None,
) -> str | list[dict[str, Any]] | None:
    """
    将 **user** 角色 ``Message`` 转为 OpenAI ``messages[].content`` 形态：
    - 纯文本（单段 text Part）：非空则返回 ``str``；
    - 多模态或多段：返回块 ``list[dict]``；
    - 无可发送内容：``None``。
    """
    if message.role != "user":
        return None
    processed = apply_user_parts_preprocessing(message.parts, session_meta=session_meta)
    tmp = Message(
        message_id=message.message_id,
        role="user",
        parts=processed,
        timestamp=message.timestamp,
        loop_index=message.loop_index,
        token_count=message.token_count,
    )
    blocks = message_to_openai_user_blocks(tmp)
    if blocks is not None:
        return blocks
    text = render_message_plain_text(tmp).strip()
    return text if text else None
