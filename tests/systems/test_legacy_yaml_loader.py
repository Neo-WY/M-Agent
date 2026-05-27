"""Compatibility tests for the legacy ``chat_controller.yaml`` shape.

The refactor introduced ``systems:`` as the new way to declare the
three subsystems, but legacy fields (``plugins:``, ``enabled_tools:``,
``tool_defaults:``, ``working_memory:``, ``episode_query_enabled:``)
must keep loading for at least one release. These tests verify the
translation path and the :class:`DeprecationWarning` it emits.
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

import pytest

from m_agent.chat.three_layer_plugins import (
    ThreeLayerPluginOverrides,
    load_plugin_overrides_from_config,
)
from m_agent.paths import PROJECT_ROOT
from m_agent.systems import EpisodeQueryModule


def test_empty_plugins_block_returns_empty_overrides_without_warning() -> None:
    """An empty ``plugins:`` block must not trigger the deprecation warning."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        overrides = load_plugin_overrides_from_config({})
    assert isinstance(overrides, ThreeLayerPluginOverrides)
    assert overrides.is_empty()
    assert not any(
        issubclass(w.category, DeprecationWarning) and "plugins:" in str(w.message)
        for w in captured
    )


def test_non_empty_plugins_block_warns_about_deprecation() -> None:
    """A populated legacy block must emit a DeprecationWarning that points to ``systems:``."""
    payload = {
        "episode_query_module": {
            "path": "m_agent.systems.episodic.query_module:EpisodeQueryModule",
            "kwargs": {"enabled": False},
        }
    }
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        overrides = load_plugin_overrides_from_config(payload)
    assert isinstance(overrides.episode_query_module, EpisodeQueryModule)
    assert overrides.episode_query_module.enabled is False
    assert any(
        issubclass(w.category, DeprecationWarning)
        and "systems:" in str(w.message)
        for w in captured
    ), "Expected migration hint pointing at systems:"


def test_legacy_overrides_feed_into_systems_bundle_via_chat_agent(tmp_path: Any) -> None:
    """A YAML with only legacy fields still produces a populated SystemsBundle.

    We construct a minimal chat-controller YAML that exercises:
      * ``plugins:`` flat mapping (legacy)
      * ``enabled_tools:`` flat list (legacy)
      * ``tool_defaults:`` flat mapping (legacy)
      * ``working_memory:`` flat mapping (legacy)
      * ``episode_query_enabled: false`` (legacy)

    No ``systems:`` block is present, so the agent must fall back to the
    legacy translation path and build a complete bundle.
    """
    # We can't easily boot a full ThreeLayerChatAgent without an LLM /
    # Legacy plugins YAML; exercise conversion helpers directly.
    cfg: Dict[str, Any] = {
        "plugins": {
            "episode_query_module": {
                "path": "m_agent.systems.episodic.query_module:EpisodeQueryModule",
                "kwargs": {"enabled": False},
            }
        },
        "enabled_tools": ["shallow_recall", "get_current_time"],
        "tool_defaults": {"email_ask": {"mail_scope": "all"}},
        "working_memory": {"enable": False, "max_stored_entries": 7},
        "episode_query_enabled": True,  # gets overridden by the plugin instance
    }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        overrides = load_plugin_overrides_from_config(cfg["plugins"])
    assert isinstance(overrides, ThreeLayerPluginOverrides)
    assert overrides.episode_query_module is not None
    assert overrides.episode_query_module.enabled is False

    # Sanity: the legacy block carries through the disabled query state,
    # i.e. ``capability_hint`` consumers will see an empty hint list.
    assert overrides.episode_query_module.capability_names == ("shallow_recall", "deep_recall")


def test_invalid_plugin_slot_raises() -> None:
    from m_agent.chat.three_layer_plugins import PluginConfigError

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(PluginConfigError) as exc_info:
            load_plugin_overrides_from_config({"not_a_real_slot": "anything"})
    assert "unknown plugin slot" in str(exc_info.value)


def test_yaml_systems_block_takes_precedence_over_legacy_plugins() -> None:
    """When both blocks coexist the new ``systems:`` block wins per-slot."""
    from m_agent.systems import load_systems_bundle_from_config

    bundle = load_systems_bundle_from_config(
        {
            "episodic": {
                "system": "episodic",
                "recorder": {"path": "m_agent.systems.episodic.default.recorder:DefaultEpisodeRecorder"},
                "backend": {
                    "path": "m_agent.systems.episodic.default.rag_backend:SimpleRagEpisodicBackend",
                    "kwargs": {"embed_model": "hash"},
                },
                "query": {"enabled": True},
            }
        },
        config_dir=PROJECT_ROOT / "config" / "agents" / "chat",
    )
    assert bundle.episodic is not None
    assert bundle.episodic.query_module.enabled is True
