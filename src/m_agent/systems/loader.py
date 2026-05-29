"""Shared loader machinery for the ``systems/`` package.

Three duties:

1. ``resolve_dotted_path`` — turn ``pkg.mod:attr`` or ``pkg.mod.attr``
   into a Python object.
2. ``materialize_plugin`` — turn a YAML plug-in spec
   (string dotted path or mapping ``{path, kwargs}``) into a live
   instance.
3. ``load_systems_bundle_from_config`` — read the top-level ``systems:``
   block of ``chat_controller.yaml`` and build a
   :class:`~m_agent.systems.bundles.SystemsBundle` by delegating each
   slot to its per-system loader.

The split keeps the chat-controller loader thin: it does not need to
know what each system contains, only that each entry is either a string
path to a system YAML or an inline mapping with the same shape.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml


class SystemsConfigError(ValueError):
    """Raised when a systems YAML or plug-in spec cannot be resolved."""


def resolve_dotted_path(spec: str) -> Any:
    """Resolve ``pkg.mod:attr`` (or ``pkg.mod.attr``) to a Python object."""
    text = str(spec or "").strip()
    if not text:
        raise SystemsConfigError("dotted path is empty")
    if ":" in text:
        module_path, _, attr_name = text.partition(":")
    elif "." in text:
        module_path, _, attr_name = text.rpartition(".")
    else:
        raise SystemsConfigError(
            f"plugin path {text!r} must contain '.' or ':' "
            "(e.g. 'pkg.mod:Class')"
        )
    module_path = module_path.strip()
    attr_name = attr_name.strip()
    if not module_path or not attr_name:
        raise SystemsConfigError(
            f"plugin path {text!r} has empty module or attribute part"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise SystemsConfigError(
            f"plugin path {text!r}: failed to import module {module_path!r}: {exc}"
        ) from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise SystemsConfigError(
            f"plugin path {text!r}: module {module_path!r} has no attribute {attr_name!r}"
        ) from exc


def materialize_plugin(
    slot: str,
    spec: Any,
    *,
    default_kwargs: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Turn a plug-in spec (string or ``{path, kwargs}`` mapping) into a live object.

    * **None / missing** — caller decides default; returns ``None``.
    * **string** dotted path — resolve + call with ``default_kwargs``
      (if any). Use a factory function when zero-arg construction is
      not enough.
    * **mapping** ``{path, kwargs}`` — resolve + call with merged kwargs
      (caller's ``default_kwargs`` plus YAML ``kwargs``; YAML wins
      per-key).
    """
    if spec is None:
        return None
    base_kwargs = dict(default_kwargs or {})
    if isinstance(spec, str):
        target = resolve_dotted_path(spec)
        try:
            return target(**base_kwargs) if base_kwargs else target()
        except TypeError as exc:
            if base_kwargs:
                raise SystemsConfigError(
                    f"systems.{slot}: {spec!r} is not callable with kwargs={base_kwargs!r}: {exc}"
                ) from exc
            raise SystemsConfigError(
                f"systems.{slot}: {spec!r} is not callable with zero args "
                f"(use the mapping form with 'kwargs' to pass arguments): {exc}"
            ) from exc
    if isinstance(spec, Mapping):
        path = spec.get("path") or spec.get("class") or spec.get("factory")
        if not isinstance(path, str) or not path.strip():
            raise SystemsConfigError(
                f"systems.{slot}: mapping requires a string 'path' (got {spec!r})"
            )
        kwargs_raw = spec.get("kwargs", {})
        if kwargs_raw is None:
            kwargs_raw = {}
        if not isinstance(kwargs_raw, Mapping):
            raise SystemsConfigError(
                f"systems.{slot}: 'kwargs' must be a mapping (got {type(kwargs_raw).__name__})"
            )
        merged_kwargs = dict(base_kwargs)
        merged_kwargs.update(dict(kwargs_raw))
        target = resolve_dotted_path(path)
        try:
            return target(**merged_kwargs) if merged_kwargs else target()
        except TypeError as exc:
            raise SystemsConfigError(
                f"systems.{slot}: failed to call {path!r} with kwargs={merged_kwargs!r}: {exc}"
            ) from exc
    raise SystemsConfigError(
        f"systems.{slot}: unsupported value type {type(spec).__name__}; "
        f"use a string dotted path or a mapping with 'path' + 'kwargs'"
    )


def load_system_yaml(path: Path, *, expected_kind: str) -> Dict[str, Any]:
    """Read a system YAML file and verify its top-level ``system`` field matches."""
    if not path.exists():
        raise SystemsConfigError(f"system config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemsConfigError(f"system config must be a mapping: {path}")
    kind = str(data.get("system", "") or "").strip().lower()
    if kind and kind != expected_kind:
        raise SystemsConfigError(
            f"system config kind mismatch at {path}: expected {expected_kind!r}, got {kind!r}"
        )
    return data


def _resolve_path(entry: str, *, base_dir: Path) -> Path:
    p = Path(entry)
    if p.is_absolute():
        return p.resolve()
    return (base_dir / p).resolve()


def load_systems_bundle_from_config(
    systems_cfg: Any,
    *,
    config_dir: Path,
) -> "SystemsBundle":
    """Build a :class:`SystemsBundle` from a chat-controller ``systems:`` mapping.

    Each slot accepts:

    * a string yaml path (recommended) — relative paths resolved
      against ``config_dir`` (i.e. the directory of ``chat_controller.yaml``).
    * a mapping — inline system config equivalent to a system yaml.
    * ``None`` / missing — caller falls back to default.
    """
    # Local imports to keep the top-level package import lightweight.
    from .bundles import SystemsBundle
    from .episodic.system import load_episodic_system
    from .tools.system import load_tool_suite_system
    from .wm.system import load_wm_system

    if systems_cfg is None:
        return SystemsBundle()
    if not isinstance(systems_cfg, Mapping):
        raise SystemsConfigError(
            f"top-level 'systems' must be a mapping (got {type(systems_cfg).__name__})"
        )
    known = {"wm", "episodic", "tools"}
    unknown = set(systems_cfg.keys()) - known
    if unknown:
        raise SystemsConfigError(
            f"unknown system slot(s): {sorted(unknown)}; valid slots: {sorted(known)}"
        )

    wm_entry = systems_cfg.get("wm")
    episodic_entry = systems_cfg.get("episodic")
    tools_entry = systems_cfg.get("tools")

    bundle_kwargs: Dict[str, Any] = {}

    if wm_entry is not None:
        source = _resolve_path(wm_entry, base_dir=config_dir) if isinstance(wm_entry, str) else wm_entry
        bundle_kwargs["wm"] = load_wm_system(source)

    if episodic_entry is not None:
        source = (
            _resolve_path(episodic_entry, base_dir=config_dir)
            if isinstance(episodic_entry, str)
            else episodic_entry
        )
        bundle_kwargs["episodic"] = load_episodic_system(source)

    if tools_entry is not None:
        source = (
            _resolve_path(tools_entry, base_dir=config_dir)
            if isinstance(tools_entry, str)
            else tools_entry
        )
        bundle_kwargs["tools"] = load_tool_suite_system(source)

    return SystemsBundle(**bundle_kwargs)


__all__ = [
    "SystemsConfigError",
    "load_system_yaml",
    "load_systems_bundle_from_config",
    "materialize_plugin",
    "resolve_dotted_path",
]
