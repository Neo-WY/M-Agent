# Config Layout

Runtime configuration for the **M-Agent chat stack**. MemoryAgent / LoCoMo eval configs are in [**WorkspaceMem**](F:/AI/WorkspaceMem).

## Developer guide

**Subsystem plug-ins (protocols, YAML, integration packages, tests):**

- [docs/systems-plugin-development.zh-CN.md](../docs/systems-plugin-development.zh-CN.md)（中文，完整）
- [docs/systems-plugin-development.md](../docs/systems-plugin-development.md)（English）

## Directories

| Path | Purpose |
|------|---------|
| `agents/chat/` | Chat controller, model, runtime prompts |
| `agents/email/`, `agents/schedule/` | Domain agents |
| `systems/` | WM / episodic / tools YAML variants |
| `prompts/examples/` | Demo only |
| `integrations/` | e.g. Neo4j |
| `users/` | Per-user generated configs (do not hand-edit others' trees) |

## Chat chain (default)

```text
agents/chat/chat_controller.yaml
  → systems/wm/default.yaml
  → systems/episodic/rag_default.yaml
  → systems/tools/default.yaml (+ runtime_descriptions.yaml)
  → chat_model.yaml, runtime/chat_controller_runtime.yaml
```

Swap a subsystem: change **one** path under `systems:` in `chat_controller.yaml`.
