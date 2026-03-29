from __future__ import annotations

from platform_layer.bundled_root import framework_root

from infra.logging_config import setup_structured_logging

from app.composition import build_port
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from app.port_mode_registry import resolve_interaction_mode
from port.agent_port import CliEmitter, InteractionMode
from port.input_events import DeviceResultInput, SystemCommandInput, UserMessageInput
from port.request_factory import cli_request_factory


def run(mode: InteractionMode) -> None:
    emitter = CliEmitter()
    port = build_port(mode=mode, request_factory=cli_request_factory(), emitter=emitter)

    while True:
        line = mode.receive()
        if line is None:
            break
        if line == "":
            continue
        if mode.should_exit(line):
            break
        if line.strip().lower().startswith("/confirm "):
            port.handle(SystemCommandInput(kind="system_command", text=line))
        elif line.strip().lower().startswith("/device_result "):
            payload = line.strip()[len("/device_result ") :]
            port.handle(DeviceResultInput(kind="device_result", payload=payload))
        else:
            port.handle(UserMessageInput(kind="user_message", text=line))


def main() -> None:
    setup_structured_logging()
    src_root = framework_root()
    rc = load_runtime_config(
        RuntimeConfigSource(path=src_root / "platform_layer" / "resources" / "config" / "runtime.yaml")
    )
    mode = resolve_interaction_mode(rc.port_interaction_mode_ref)
    run(mode)


if __name__ == "__main__":
    main()

