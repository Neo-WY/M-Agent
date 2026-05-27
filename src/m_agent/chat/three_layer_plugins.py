"""DEPRECATED — legacy ``plugins:`` mapping translator.

This module used to be the single source of truth for the
three-layer chat agent's plug-in slots. It has been superseded by the
**systems** package (:mod:`m_agent.systems`), which organises the same
plug-in points into three subsystems and one aggregate
:class:`~m_agent.systems.SystemsBundle`.

For backward compatibility this module still exposes:

* :class:`ThreeLayerPluginOverrides` — programmatic override container.
  Internally it is a thin adapter over :class:`SystemsBundle`.
* :func:`load_plugin_overrides_from_config` — parse a flat ``plugins:``
  YAML section into a :class:`ThreeLayerPluginOverrides`. Existing
  ``chat_controller.yaml`` files that still use ``plugins:`` will keep
  working, with a :class:`DeprecationWarning`.

New code should construct a :class:`SystemsBundle` directly.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from m_agent.systems import (
    ControllerCapabilityRegistry,
    EpisodeQueryModule,
    EpisodeRecorder,
    SystemsBundle,
    SystemsConfigError,
    WMReader,
    WMWriter,
    materialize_plugin,
    resolve_dotted_path as _resolve_dotted_path,
)


logger = logging.getLogger(__name__)


_VALID_PLUGIN_SLOTS = frozenset(
    {
        "wm_writer",
        "wm_reader",
        "episode_recorder",
        "episode_query_module",
        "capability_registry",
    }
)


_SLOT_EXPECTED_TYPE: Dict[str, type] = {
    "wm_writer": WMWriter,
    "wm_reader": WMReader,
    "episode_recorder": EpisodeRecorder,
    "episode_query_module": EpisodeQueryModule,
    "capability_registry": ControllerCapabilityRegistry,
}


# ``PluginConfigError`` is the legacy alias. The new package raises
# :class:`SystemsConfigError`; aliasing them keeps both ``except`` clauses
# valid during the migration window.
PluginConfigError = SystemsConfigError


@dataclass
class ThreeLayerPluginOverrides:
    """DEPRECATED — programmatic override container.

    Prefer building a :class:`SystemsBundle` directly. This class
    remains as an adapter so existing call sites
    (``create_three_layer_chat_agent(plugins=...)``) keep working.
    """

    wm_writer: Optional[WMWriter] = None
    wm_reader: Optional[WMReader] = None
    episode_recorder: Optional[EpisodeRecorder] = None
    episode_query_module: Optional[EpisodeQueryModule] = None
    capability_registry: Optional[ControllerCapabilityRegistry] = None

    def merge_with_yaml(
        self, yaml_overrides: "ThreeLayerPluginOverrides"
    ) -> "ThreeLayerPluginOverrides":
        """Per-slot merge: ``self`` wins, then ``yaml_overrides``."""
        return ThreeLayerPluginOverrides(
            wm_writer=self.wm_writer or yaml_overrides.wm_writer,
            wm_reader=self.wm_reader or yaml_overrides.wm_reader,
            episode_recorder=self.episode_recorder or yaml_overrides.episode_recorder,
            episode_query_module=self.episode_query_module
            or yaml_overrides.episode_query_module,
            capability_registry=self.capability_registry
            or yaml_overrides.capability_registry,
        )

    def is_empty(self) -> bool:
        return all(
            getattr(self, slot) is None
            for slot in (
                "wm_writer",
                "wm_reader",
                "episode_recorder",
                "episode_query_module",
                "capability_registry",
            )
        )


def _materialize_plugin(slot: str, spec: Any) -> Any:
    """Adapter around :func:`m_agent.systems.materialize_plugin` for the legacy slot names."""
    return materialize_plugin(slot, spec)


def load_plugin_overrides_from_config(
    plugins_cfg: Any,
) -> ThreeLayerPluginOverrides:
    """Parse a legacy ``plugins:`` YAML mapping into a :class:`ThreeLayerPluginOverrides`.

    A :class:`DeprecationWarning` is emitted when ``plugins_cfg`` is
    non-empty so external configs migrate to ``systems:`` over time.
    """
    if plugins_cfg is None:
        return ThreeLayerPluginOverrides()
    if not isinstance(plugins_cfg, Mapping):
        raise PluginConfigError(
            f"top-level 'plugins' must be a mapping (got {type(plugins_cfg).__name__})"
        )

    if plugins_cfg:
        warnings.warn(
            "chat_controller.yaml `plugins:` mapping is deprecated; "
            "migrate to the `systems:` block (see config/systems/README.md).",
            DeprecationWarning,
            stacklevel=2,
        )

    unknown = set(plugins_cfg.keys()) - _VALID_PLUGIN_SLOTS
    if unknown:
        raise PluginConfigError(
            f"unknown plugin slot(s): {sorted(unknown)}; valid slots: {sorted(_VALID_PLUGIN_SLOTS)}"
        )

    materialised: Dict[str, Any] = {}
    for slot in _VALID_PLUGIN_SLOTS:
        if slot not in plugins_cfg:
            continue
        try:
            instance = _materialize_plugin(slot, plugins_cfg[slot])
        except ValueError as exc:
            raise PluginConfigError(str(exc)) from exc
        if instance is None:
            continue
        materialised[slot] = instance

    return ThreeLayerPluginOverrides(**materialised)


def describe_plugin_protocols() -> str:
    """Return a human-readable summary of the legacy plug-in slots."""
    lines = ["Three-layer plug-in slots (DEPRECATED — see m_agent.systems):"]
    for slot, expected in sorted(_SLOT_EXPECTED_TYPE.items()):
        lines.append(f"  - {slot:<22s}  expects: {expected.__module__}.{expected.__name__}")
    return "\n".join(lines)


__all__ = [
    "PluginConfigError",
    "ThreeLayerPluginOverrides",
    "describe_plugin_protocols",
    "load_plugin_overrides_from_config",
]
