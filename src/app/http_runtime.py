from __future__ import annotations

from typing import Any

from app.http_app_factory import HttpAgentService, InputDTO, build_http_agent_service
from infra.logging_config import setup_structured_logging

setup_structured_logging()

_http_port_cell: list[Any] = [None]
_bundle: HttpAgentService = build_http_agent_service(port_cell=_http_port_cell)
app = _bundle.app

__all__ = ["InputDTO", "app", "main", "_http_port_cell"]


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
