from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from platform_layer.bundled_root import framework_root

from app.composition import build_core
from app.config_provider import yaml_file_config_provider
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from app.version import __version__
from core import AgentCoreImpl
from port.agent_port import GenericAgentPort, HttpMode
from port.events import ErrorEvent
from port.http_emitter import HttpEmitter
from port.input_events import DeviceResultInput, SystemCommandInput, UserMessageInput
from port.request_factory import cli_request_factory


@dataclass(frozen=True)
class InputDTO:
    """与 ``POST /input``、``WS /ws`` 入站 JSON 同构的请求体（供类型标注与复用）。"""

    kind: Literal["user_message", "system_command", "device_result"]
    user_id: str = "http-user"
    channel: str = "http"
    text: str | None = None
    payload: str | None = None
    openai_user_content: list[dict[str, Any]] | None = None
    stream: bool = False


@dataclass(frozen=True)
class HttpAgentService:
    """HTTP/WS 实验性服务装配结果：可挂载或交给 ``uvicorn`` 运行。"""

    app: FastAPI
    kernel: AgentCoreImpl
    port: GenericAgentPort


def build_http_agent_service(
    *,
    src_root: Path | None = None,
    kernel: AgentCoreImpl | None = None,
    port_cell: list[Any] | None = None,
) -> HttpAgentService:
    """
    装配与 ``app.http_runtime`` 默认行为一致的 FastAPI 应用。

    - ``kernel``：若传入则复用已有内核（例如与 CLI/自定义路由共用会话与配置）。
    - ``src_root``：配置树根（含 ``platform_layer/resources``）；默认随包 ``framework_root()``。
    - ``port_cell``：单元素列表，``[0]`` 在装配后指向 ``GenericAgentPort``；测试可通过替换 ``[0]`` 注入假 Port（``app.http_runtime`` 传入共享列表）。
    """
    cell: list[Any] = port_cell if port_cell is not None else [None]
    base = src_root if src_root is not None else framework_root()
    runtime_config = load_runtime_config(
        RuntimeConfigSource(path=base / "platform_layer" / "resources" / "config" / "runtime.yaml")
    )
    if kernel is None:
        session_config_path = base / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
        model_registry = load_model_registry(
            ModelProviderSource(path=base / "platform_layer" / "resources" / "config" / "model_providers.yaml")
        )
        core = build_core(
            config_provider=yaml_file_config_provider(session_config_path),
            model_registry=model_registry,
            src_root=base,
        )
    else:
        core = kernel
    pending_sqlite = (
        (base / runtime_config.pending_state_sqlite_path)
        if runtime_config.pending_state_backend == "sqlite_shared"
        else None
    )
    http_port = GenericAgentPort(
        mode=HttpMode(),
        core=core,
        request_factory=cli_request_factory(),
        emitter=HttpEmitter(),
        pending_state_sqlite_path=pending_sqlite,
    )
    cell[0] = http_port

    def handle_dto(dto: InputDTO) -> list[dict[str, Any]]:
        emitter = HttpEmitter()
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

        port = cell[0]
        kind_actions = {
            "user_message": lambda: port.handle(
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
            "system_command": lambda: port.handle(
                SystemCommandInput(kind="system_command", text=dto.text or ""),
                user_id=dto.user_id,
                channel=dto.channel,
                emitter=emitter,
            ),
            "device_result": lambda: port.handle(
                DeviceResultInput(kind="device_result", payload=dto.payload or ""),
                user_id=dto.user_id,
                channel=dto.channel,
                emitter=emitter,
            ),
        }
        kind_actions[dto.kind]()
        return emitter.dump()

    fastapi_app = FastAPI(title=f"Pompeii-Agent (experimental http) v{__version__}")

    @fastapi_app.get("/health")
    def health() -> dict[str, Any]:
        return JSONResponse({"ok": True, "version": __version__}, media_type="application/json; charset=utf-8")

    @fastapi_app.get("/archives")
    def http_list_archives(
        user_id: str = Query(..., min_length=1),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        items = core.list_archives_for_user(user_id, limit=limit)
        return JSONResponse(
            {"ok": True, "version": __version__, "user_id": user_id, "archives": items},
            media_type="application/json; charset=utf-8",
        )

    @fastapi_app.post("/input")
    def handle_input(dto: InputDTO) -> dict[str, Any]:
        return JSONResponse({"events": handle_dto(dto)}, media_type="application/json; charset=utf-8")

    @fastapi_app.websocket("/ws")
    async def ws_input(websocket: WebSocket) -> None:
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
                ws_dto = InputDTO(
                    kind=str(payload.get("kind", "user_message")),
                    user_id=str(payload.get("user_id", "http-user")),
                    channel=str(payload.get("channel", "http")),
                    text=str(payload["text"]) if payload.get("text") is not None else None,
                    payload=str(payload["payload"]) if payload.get("payload") is not None else None,
                    openai_user_content=payload.get("openai_user_content"),
                    stream=bool(payload.get("stream", False)),
                )
                await websocket.send_json({"events": handle_dto(ws_dto)})
        except WebSocketDisconnect:
            return

    return HttpAgentService(app=fastapi_app, kernel=core, port=http_port)
