from __future__ import annotations

__all__ = [
    "DEFAULT_CHAT_CONFIG_PATH",
    "PluginConfigError",
    "ThreeLayerChatAgent",
    "ThreeLayerPluginOverrides",
    "create_chat_agent",
    "create_three_layer_chat_agent",
    "load_plugin_overrides_from_config",
]


def __getattr__(name: str):
    if name in {"DEFAULT_CHAT_CONFIG_PATH", "create_chat_agent"}:
        from .chat_agent_factory import DEFAULT_CHAT_CONFIG_PATH, create_chat_agent

        return {
            "DEFAULT_CHAT_CONFIG_PATH": DEFAULT_CHAT_CONFIG_PATH,
            "create_chat_agent": create_chat_agent,
        }[name]
    if name in {"ThreeLayerChatAgent", "create_three_layer_chat_agent"}:
        from .three_layer_chat_agent import (
            ThreeLayerChatAgent,
            create_three_layer_chat_agent,
        )

        return {
            "ThreeLayerChatAgent": ThreeLayerChatAgent,
            "create_three_layer_chat_agent": create_three_layer_chat_agent,
        }[name]
    if name in {
        "PluginConfigError",
        "ThreeLayerPluginOverrides",
        "load_plugin_overrides_from_config",
    }:
        from .three_layer_plugins import (
            PluginConfigError,
            ThreeLayerPluginOverrides,
            load_plugin_overrides_from_config,
        )

        return {
            "PluginConfigError": PluginConfigError,
            "ThreeLayerPluginOverrides": ThreeLayerPluginOverrides,
            "load_plugin_overrides_from_config": load_plugin_overrides_from_config,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
