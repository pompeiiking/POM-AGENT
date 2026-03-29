from __future__ import annotations

from pathlib import Path


def framework_root() -> Path:
    """
    返回「安装根目录」：其下存在 ``platform_layer/resources``（开发时等同于仓库的 ``src/``）。

    用于 ``pip install`` / 可编辑安装后可靠定位随包分发的默认配置，而不仅依赖 ``app`` 包在磁盘上的相对位置。
    """
    return Path(__file__).resolve().parent.parent
