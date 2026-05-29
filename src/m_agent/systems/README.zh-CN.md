# `m_agent.systems`

对话栈的可插拔 **WM / 情景记忆 / 工具** 子系统。

**开发指南（唯一详细文档）：** [docs/systems-plugin-development.zh-CN.md](../../../docs/systems-plugin-development.zh-CN.md) · [English](../../../docs/systems-plugin-development.md)

Chat 情景记忆默认落盘：`data/memory/chat-api/<用户>/episodic/`（RAG）；对话 JSON：`.../dialogues/`。见开发指南 **§3.4.1**。

**配置目录：** [config/systems/README.md](../../../config/systems/README.md)

常用导入：

```python
from m_agent.systems import (
    SystemsBundle,
    load_systems_bundle_from_config,
    WMSystem,
    EpisodicMemorySystem,
    ToolSuiteSystem,
)
```
