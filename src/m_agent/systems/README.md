# `m_agent.systems`

Pluggable **WM / episodic / tools** subsystems for the chat stack.

**Developer guide (canonical):** [docs/systems-plugin-development.md](../../../docs/systems-plugin-development.md) · [中文版](../../../docs/systems-plugin-development.zh-CN.md)

**Config layout:** [config/systems/README.md](../../../config/systems/README.md)

Quick import:

```python
from m_agent.systems import (
    SystemsBundle,
    load_systems_bundle_from_config,
    WMSystem,
    EpisodicMemorySystem,
    ToolSuiteSystem,
)
```
