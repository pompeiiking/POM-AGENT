from __future__ import annotations

from app.composition import build_port
from port.agent_port import CliEmitter, CliMode, InteractionMode
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
    run(CliMode())


if __name__ == "__main__":
    main()

