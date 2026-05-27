"""M-Agent pluggable subsystems.

The chat stack is built from **three pluggable subsystems** that
together expose **six access points**:

* :class:`WMSystem` — working-memory subsystem.
    * ``writer`` :class:`WMWriter`
    * ``reader`` :class:`WMReader`
    * ``display`` :class:`WMDisplay`
* :class:`EpisodicMemorySystem` — episodic-memory subsystem.
    * ``recorder`` :class:`EpisodeRecorder`
    * ``backend`` :class:`EpisodicMemoryBackend`
    * ``query_module`` :class:`EpisodeQueryModule` (on/off switch)
* :class:`ToolSuiteSystem` — top-level tool suite.
    * ``registry`` :class:`ControllerCapabilityRegistry`

Each subsystem owns its own YAML file under ``config/systems/<name>/``;
the chat-controller main YAML only holds three string pointers
(``systems.wm`` / ``systems.episodic`` / ``systems.tools``). Switching
a subsystem = swapping a single line in the chat-controller config.

See :class:`SystemsBundle` for the programmatic override entry point,
and :func:`load_systems_bundle_from_config` for the YAML one.
"""
from __future__ import annotations

from .bundles import SystemsBundle
from .episodic import (
    DefaultEpisodeRecorder,
    EPISODE_QUERY_CAPABILITY_NAMES,
    EpisodeQueryModule,
    EpisodeRecorder,
    EpisodeRecorderNoop,
    EpisodicMemoryBackend,
    EpisodicMemorySystem,
    SimpleRagEpisodicBackend,
    build_default_episodic_system,
    load_episodic_system,
)
from .loader import (
    SystemsConfigError,
    load_systems_bundle_from_config,
    materialize_plugin,
    resolve_dotted_path,
)
from .tools import (
    ControllerCapabilityContext,
    ControllerCapabilityRegistry,
    ControllerCapabilitySpec,
    ToolSuiteSystem,
    build_controller_tools,
    build_default_tool_suite_system,
    get_default_capability_registry,
    load_tool_suite_system,
    register_capability,
    resolve_enabled_controller_capability_names,
)
from .wm import (
    DefaultWMDisplay,
    DefaultWMReader,
    DefaultWMWriter,
    WMDisplay,
    WMReader,
    WMSystem,
    WMWriter,
    build_default_wm_system,
    load_wm_system,
)

__all__ = [
    # Bundle / loader
    "SystemsBundle",
    "SystemsConfigError",
    "load_systems_bundle_from_config",
    "materialize_plugin",
    "resolve_dotted_path",
    # WM system
    "DefaultWMDisplay",
    "DefaultWMReader",
    "DefaultWMWriter",
    "WMDisplay",
    "WMReader",
    "WMSystem",
    "WMWriter",
    "build_default_wm_system",
    "load_wm_system",
    # Episodic system
    "DefaultEpisodeRecorder",
    "SimpleRagEpisodicBackend",
    "EPISODE_QUERY_CAPABILITY_NAMES",
    "EpisodeQueryModule",
    "EpisodeRecorder",
    "EpisodeRecorderNoop",
    "EpisodicMemoryBackend",
    "EpisodicMemorySystem",
    "build_default_episodic_system",
    "load_episodic_system",
    # Tool suite
    "ControllerCapabilityContext",
    "ControllerCapabilityRegistry",
    "ControllerCapabilitySpec",
    "ToolSuiteSystem",
    "build_controller_tools",
    "build_default_tool_suite_system",
    "get_default_capability_registry",
    "load_tool_suite_system",
    "register_capability",
    "resolve_enabled_controller_capability_names",
]
