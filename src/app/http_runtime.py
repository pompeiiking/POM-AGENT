from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.composition import build_core
from app.version import __version__
from infra.logging_config import setup_structured_logging
from app.config_provider import yaml_file_config_provider
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from port.agent_port import GenericAgentPort, HttpMode
from port.events import ErrorEvent
from port.http_emitter import HttpEmitter
from port.input_events import DeviceResultInput, SystemCommandInput, UserMessageInput
from port.request_factory import cli_request_factory

setup_structured_logging()

@dataclass(frozen=True)
class InputDTO:
    kind: Literal["user_message", "system_command", "device_result"]
    user_id: str = "http-user"
    channel: str = "http"
    text: str | None = None
    payload: str | None = None
    # OpenAI Chat 风格多模态 user 块；与 text 并存时 text 可作说明（可为空字符串）
    openai_user_content: list[dict[str, Any]] | None = None
    # 为真时，若 model provider 的 params.stream 为真且未带 tools，则走 OpenAI 兼容流式并在 events 中产出 stream_delta
    stream: bool = False


def _handle_dto(dto: InputDTO) -> list[dict[str, Any]]:
    emitter = HttpEmitter()
    # user_message 必须带 text 键（可为空字符串）；纯多模态时可 text="" 但须提供 openai_user_content
    if dto.kind == "user_message" and dto.text is None:
        emitter.emit(
            ErrorEvent(
                kind="error",
                message="user_message requires a `text` field (use empty string to send an empty message)",
                reason="validation_missing_text",
            )
        )
        return emitter.dump()
    if dto.kind == "user_message":
        mm = dto.openai_user_content
        has_mm = bool(mm and len(mm) > 0)
        if not (dto.text or "").strip() and not has_mm:
            emitter.emit(
                ErrorEvent(
                    kind="error",
                    message="user_message requires non-empty `text` or a non-empty `openai_user_content` list",
                    reason="validation_empty_payload",
                )
            )
            return emitter.dump()

    kind_actions = {
        "user_message": lambda: _HTTP_PORT.handle(
            UserMessageInput(
                kind="user_message",
                text=dto.text or "",
                stream=dto.stream,
                openai_user_content=tuple(dto.openai_user_content) if dto.openai_user_content else None,
            ),
            user_id=dto.user_id,
            channel=dto.channel,
            emitter=emitter,
        ),
        "system_command": lambda: _HTTP_PORT.handle(
            SystemCommandInput(kind="system_command", text=dto.text or ""),
            user_id=dto.user_id,
            channel=dto.channel,
            emitter=emitter,
        ),
        "device_result": lambda: _HTTP_PORT.handle(
            DeviceResultInput(kind="device_result", payload=dto.payload or ""),
            user_id=dto.user_id,
            channel=dto.channel,
            emitter=emitter,
        ),
    }
    kind_actions[dto.kind]()
    return emitter.dump()


app = FastAPI(title=f"Pompeii-Agent (experimental http) v{__version__}")


# ============================================================
# 预先装配一次 Core（会话存储为 SQLite，路径见 runtime.yaml）
# ============================================================
_BASE = Path(__file__).resolve().parents[1]  # .../<repo>/src
_SESSION_CONFIG_PATH = _BASE / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
_MODEL_REGISTRY = load_model_registry(ModelProviderSource(path=_BASE / "platform_layer" / "resources" / "config" / "model_providers.yaml"))
_RUNTIME_CONFIG = load_runtime_config(
    RuntimeConfigSource(path=_BASE / "platform_layer" / "resources" / "config" / "runtime.yaml")
)
_CORE = build_core(
    config_provider=yaml_file_config_provider(_SESSION_CONFIG_PATH),
    model_registry=_MODEL_REGISTRY,
    src_root=_BASE,
)

# 与 Core 同生命周期复用 Port，使待确认/待设备状态在多次 HTTP 请求间保持（按 user_id+channel 分区）
_HTTP_PORT = GenericAgentPort(
    mode=HttpMode(),
    core=_CORE,
    request_factory=cli_request_factory(),
    emitter=HttpEmitter(),
    pending_state_sqlite_path=(
        (_BASE / _RUNTIME_CONFIG.pending_state_sqlite_path)
        if _RUNTIME_CONFIG.pending_state_backend == "sqlite_shared"
        else None
    ),
)


@app.get("/health")
def health() -> dict[str, Any]:
    return JSONResponse({"ok": True, "version": __version__}, media_type="application/json; charset=utf-8")


@app.get("/archives")
def http_list_archives(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    items = _CORE.list_archives_for_user(user_id, limit=limit)
    return JSONResponse(
        {"ok": True, "version": __version__, "user_id": user_id, "archives": items},
        media_type="application/json; charset=utf-8",
    )


@app.post("/input")
def handle_input(dto: InputDTO) -> dict[str, Any]:
    return JSONResponse({"events": _handle_dto(dto)}, media_type="application/json; charset=utf-8")


@app.websocket("/ws")
async def ws_input(websocket: WebSocket) -> None:
    """
    WebSocket MVP：每条入站 JSON 与 POST /input 同构（kind/user_id/channel/text/payload/...），
    每收到一条消息回传一帧 {"events":[...]}。
    """
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await websocket.send_json(
                    {
                        "events": [
                            {
                                "kind": "error",
                                "message": "ws payload must be a JSON object",
                                "reason": "validation_ws_payload_type",
                            }
                        ]
                    }
                )
                continue
            dto = InputDTO(
                kind=str(payload.get("kind", "user_message")),
                user_id=str(payload.get("user_id", "http-user")),
                channel=str(payload.get("channel", "http")),
                text=str(payload["text"]) if payload.get("text") is not None else None,
                payload=str(payload["payload"]) if payload.get("payload") is not None else None,
                openai_user_content=payload.get("openai_user_content"),
                stream=bool(payload.get("stream", False)),
            )
            await websocket.send_json({"events": _handle_dto(dto)})
    except WebSocketDisconnect:
        return


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

