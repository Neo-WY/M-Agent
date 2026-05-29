"""On/off switch for episodic recall capabilities in the execution layer.

When the module is disabled, the execution layer behaves as if the
bundled capabilities (``shallow_recall`` / ``deep_recall``) did not
exist:

* ``describe_capabilities()`` does not list them.
* They are removed from the enabled-tools whitelist.
* The system-prompt capability section omits them entirely.

This "transparent disable" semantics keeps the thinking layer from
trying to ask for a recall it would be denied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


EPISODE_QUERY_CAPABILITY_NAMES = ("shallow_recall", "deep_recall")


@dataclass(frozen=True)
class EpisodeQueryModule:
    """Configuration of the episode-query module switch."""

    enabled: bool = True
    capability_names: tuple = field(default=EPISODE_QUERY_CAPABILITY_NAMES)

    def filter_capability_names(self, names: Iterable[str]) -> List[str]:
        """Return ``names`` with episode-query capabilities removed when disabled."""
        normalized = [str(n or "").strip() for n in names]
        normalized = [n for n in normalized if n]
        if self.enabled:
            return normalized
        blocked = {str(name or "").strip() for name in self.capability_names}
        return [name for name in normalized if name not in blocked]

    def is_blocked(self, capability_name: str) -> bool:
        """Return ``True`` when ``capability_name`` is part of this module and the switch is off."""
        if self.enabled:
            return False
        return str(capability_name or "").strip() in {
            str(name or "").strip() for name in self.capability_names
        }


__all__ = ["EPISODE_QUERY_CAPABILITY_NAMES", "EpisodeQueryModule"]
