"""Top-level factory for the chat agent.

The chat runtime uses a single implementation:
:class:`~m_agent.chat.three_layer_chat_agent.ThreeLayerChatAgent`.

``create_chat_agent`` exists for two reasons:

* it is the documented entry point used by :class:`ChatServiceRuntime` and
  external callers, so keeping the name stable avoids churning every import
  site whenever the agent's constructor gains a new keyword;
* it provides a single place to type-check the optional
  :class:`ThreeLayerPluginOverrides` so plug-in misuse fails before the
  agent boots LLM clients.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from m_agent.config_paths import DEFAULT_CHAT_AGENT_CONFIG_PATH
from m_agent.systems import SystemsBundle

from .three_layer_chat_agent import ThreeLayerChatAgent
from .three_layer_plugins import ThreeLayerPluginOverrides


logger = logging.getLogger(__name__)

#: Default chat-controller YAML path (re-exported for ergonomic imports such
#: as ``from m_agent.chat import DEFAULT_CHAT_CONFIG_PATH``).
DEFAULT_CHAT_CONFIG_PATH = DEFAULT_CHAT_AGENT_CONFIG_PATH


def create_chat_agent(
    config_path: str | Path = DEFAULT_CHAT_CONFIG_PATH,
    *,
    systems: Optional[SystemsBundle] = None,
    plugins: Optional[ThreeLayerPluginOverrides] = None,
) -> ThreeLayerChatAgent:
    """Construct the three-layer chat agent.

    Parameters
    ----------
    config_path:
        Path to ``chat_controller.yaml`` (defaults to the bundled example).
    systems:
        Optional :class:`~m_agent.systems.SystemsBundle` for programmatic
        subsystem injection. Slots left as ``None`` fall back to the YAML
        ``systems:`` block, then to legacy ``plugins:`` / defaults. This is
        the preferred way to swap a subsystem from Python code.
    plugins:
        Legacy :class:`ThreeLayerPluginOverrides` shape, kept for backward
        compatibility. Adapted into ``SystemsBundle`` internally. Prefer
        ``systems=`` for new code.
    """
    if systems is not None and not isinstance(systems, SystemsBundle):
        raise TypeError(
            "create_chat_agent: `systems` must be a SystemsBundle "
            f"(got {type(systems).__name__})"
        )
    if plugins is not None and not isinstance(plugins, ThreeLayerPluginOverrides):
        raise TypeError(
            "create_chat_agent: `plugins` must be a ThreeLayerPluginOverrides "
            f"(got {type(plugins).__name__})"
        )
    return ThreeLayerChatAgent(
        config_path=config_path,
        systems=systems,
        plugins=plugins,
    )


__all__ = ["DEFAULT_CHAT_CONFIG_PATH", "create_chat_agent"]
