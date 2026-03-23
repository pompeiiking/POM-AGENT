from __future__ import annotations

from .config import ModelProvider, ModelRegistry

__all__ = ["ModelModule", "ModelOutput", "ModelProvider", "ModelRegistry"]


def __getattr__(name: str):
    if name == "ModelModule":
        from .interface import ModelModule

        return ModelModule
    if name == "ModelOutput":
        from .interface import ModelOutput

        return ModelOutput
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
