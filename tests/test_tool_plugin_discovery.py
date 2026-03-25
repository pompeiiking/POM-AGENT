from __future__ import annotations

from modules.tools.plugin_discovery import discover_entrypoint_handlers


def test_discover_entrypoint_handlers(monkeypatch) -> None:
    def _handler(session, tool_call):  # noqa: ANN001
        return (session, tool_call)

    class _EP:
        def __init__(self, name: str):
            self.name = name

        def load(self):
            return _handler

    class _EPS:
        def select(self, *, group: str):
            if group == "pompeii_agent.tools":
                return [_EP("foo")]
            return []

    monkeypatch.setattr("modules.tools.plugin_discovery.entry_points", lambda: _EPS())
    handlers = discover_entrypoint_handlers(group="pompeii_agent.tools")
    assert "foo" in handlers
    assert callable(handlers["foo"])
