# Subsystem configs (`config/systems/`)

One YAML file = one loaded subsystem instance. The chat controller only holds **three pointers** (`systems.wm` / `episodic` / `tools`).

**Full development spec (YAML fields, protocols, examples, PR checklist):**

- [docs/systems-plugin-development.zh-CN.md](../../docs/systems-plugin-development.zh-CN.md)
- [docs/systems-plugin-development.md](../../docs/systems-plugin-development.md)

## Shipped files

```
wm/default.yaml
episodic/rag_default.yaml   # Chat 运行时 RAG 路径会重绑到 data/memory/chat-api/<user>/episodic/
tools/default.yaml
tools/runtime_descriptions.yaml
```

Per-user dialogue + episodic paths: [docs/systems-plugin-development.zh-CN.md §3.4.1](../../docs/systems-plugin-development.zh-CN.md).

## Quick swap

```yaml
# config/agents/chat/chat_controller.yaml
systems:
  episodic: ../../systems/episodic/my_variant.yaml
```

Do not inline subsystem parameters in `chat_controller.yaml`.
