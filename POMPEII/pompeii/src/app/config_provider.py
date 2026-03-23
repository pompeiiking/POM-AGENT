from __future__ import annotations

from pathlib import Path
from typing import Callable

from core import SessionConfig
from app.config_loaders.session_config_loader import SessionConfigSource, load_session_config

# 说明：
# - 提供“配置提供者”的工厂，供装配层/入口层注入到 AgentCore
# - 这里放在 app 层而非 port 层，以避免 I/O 入口与配置来源策略耦合

ConfigProvider = Callable[[str, str], SessionConfig]


def yaml_file_config_provider(config_path: Path) -> ConfigProvider:
    """
    基于指定 YAML 文件的配置提供者工厂。
    """

    def _provider(user_id: str, channel: str) -> SessionConfig:
        # 可根据 user_id / channel 做分流，这里先统一返回同一路径
        return load_session_config(SessionConfigSource(path=config_path))

    return _provider

