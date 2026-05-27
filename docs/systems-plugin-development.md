# Pluggable Subsystems — Developer Guide (`m_agent.systems` + `config/systems`)

> 中文版：[systems-plugin-development.zh-CN.md](./systems-plugin-development.zh-CN.md)

This is the **canonical** guide for external developers: how to add or swap WM, episodic-memory, and tool-suite integrations, and how to wire them through `config/systems/*.yaml`.

- **Code:** `src/m_agent/systems/`
- **Config:** `config/systems/`
- **Mount point:** `config/agents/chat/chat_controller.yaml` → `systems:` (three paths only)

**Out of scope here:** full MemoryAgent / MemoryCore / LoCoMo eval → [**WorkspaceMem**](F:/AI/WorkspaceMem).

---

## 1. Rules of the road

| Rule | Detail |
|------|--------|
| Single plug-in surface | Replaceable pieces go through `m_agent.systems`; do not patch `layers/` or `chat/` to reach a backend. |
| No inline subsystem params | `chat_controller.yaml` holds **paths only**; all knobs live in per-system YAML files. |
| Skeleton vs integration package | `protocols.py` + `system.py` at subsystem root; implementations under `default/` or your own package directory. |
| Do not experiment in `default/` | Fork a new subpackage + YAML for private variants. |
| Duck-typed protocols | No inheritance required; loader validates with `@runtime_checkable`. |

---

## 2. Architecture

### Config + load chain

```text
chat_controller.yaml  →  systems.{wm,episodic,tools}  →  load_*_system()
  →  SystemsBundle  →  ThreeLayerChatAgent  →  ThinkingAgent / ExecutionAgent
```

### Source layout

See [systems-plugin-development.zh-CN.md §2.3](./systems-plugin-development.zh-CN.md) (same tree).

### Six access points

| System | Field | Protocol | Shipped `path` |
|--------|-------|----------|----------------|
| `WMSystem` | `writer` / `reader` / `display` | `WMWriter` / `WMReader` / `WMDisplay` | `wm.default.defaults:*` |
| `EpisodicMemorySystem` | `recorder` / `backend` | `EpisodeRecorder` / `EpisodicMemoryBackend` | `episodic.default.*` |
| `EpisodicMemorySystem` | `query_module` | `EpisodeQueryModule` | YAML `query:` only |
| `ToolSuiteSystem` | `registry` | `ControllerCapabilityRegistry` | `tools.default.registry:get_default_capability_registry` |

`ToolSuiteSystem` also has `enabled`, `defaults`, `runtime_descriptions` in YAML.

---

## 3. YAML reference (summary)

Full tables and Chinese prose: [zh-CN guide §3](./systems-plugin-development.zh-CN.md).

**Common**

- Top-level `system: wm | episodic | tools`
- Slots: string `path` or `{ path, kwargs }`
- Loader does **not** expand `${ENV}` placeholders

**Chat controller** (`config/agents/chat/chat_controller.yaml`)

- Must have `systems.wm`, `systems.episodic`, `systems.tools` paths
- Must **not** duplicate `enabled_tools`, `working_memory`, etc. (legacy still accepted in old user files)

**Swap implementation:** change one line under `systems:`.

**On-disk defaults**

| File | Role |
|------|------|
| `config/systems/wm/default.yaml` | WM reader/writer/display + `config:` block |
| `config/systems/episodic/rag_default.yaml` | RAG backend kwargs |
| `config/systems/tools/default.yaml` | registry, enabled, defaults |
| `config/systems/tools/runtime_descriptions.yaml` | execution-layer tool descriptions |

---

## 4. Delivery checklist

1. Pick subsystem (`wm` / `episodic` / `tools`).
2. Implement protocol in-repo (`systems/<name>/<package>/`) or external pip package.
3. Export symbols referenced by YAML `path`.
4. Copy nearest variant YAML → `my_variant.yaml`, edit `path`/`kwargs`.
5. Point `chat_controller.yaml` `systems.<name>` at it.
6. Run `pytest tests/systems/` (+ checklist in §7 of zh-CN doc).
7. Do not patch `default/` for one-off trials.

---

## 5. Implementation notes (by subsystem)

### WM

- `WMWriter.write` mutates `entries`; `WMReader.render` → thinking layer; `WMDisplay.render` → execution layer (default: same tail-N as reader).
- Loader injects `config=WorkingMemoryConfig` into reader/writer/display constructors.

### Episodic

- Backend: `shallow_recall`, `deep_recall`, `persist_round`, `persist_dialogue`, `on_flush`.
- Recorder: `append`, `flush`; runtime drains buffer → `on_flush`.
- Recall tools call `context.get_episodic_backend()` only.

**Chat stack — per-user persistence (see [zh-CN §3.4.1](./systems-plugin-development.zh-CN.md))**

- Dialogue JSON: `data/memory/chat-api/<user>/dialogues/` (on successful flush).
- RAG index: `data/memory/chat-api/<user>/episodic/` (`chunks.jsonl`, `embeddings.npy`); written on each `persist_round` and on flush `persist_dialogue`.
- `ThreeLayerChatAgent` rebinding overrides YAML `storage_dir`/`workflow_id` at runtime.
- Inspect paths via `thread_state.episodic_persistence` on `GET .../memory/state`.
- Writing dialogue files alone does **not** build embeddings.

### Tools

- `ControllerCapabilitySpec` + `build_tool(context, description)`.
- Use `context.check_tool_call_limits`, `start_tool_call`, `finish_tool_call`.
- Prefer isolated `build_my_registry()` over global `register_capability()`.

Detailed examples (semantic WM reader, remote backend, custom capability): **zh-CN guide §5** or previous `src/m_agent/systems/README.md` content now merged there.

---

## 6. Override precedence

`systems=` arg → legacy `plugins=` → YAML `systems:` → legacy flat fields → built-in defaults.

```python
from m_agent.systems import SystemsBundle, load_episodic_system
bundle = SystemsBundle(episodic=load_episodic_system({...}))
```

---

## 7. Testing

```bash
pytest tests/systems/
```

See zh-CN §7 for file-level map and PR checklist.

---

## 8. Pitfalls

Wrong dotted path · kwargs mismatch · `query.enabled` vs recall tools mismatch · global registry mutation · bypassing episodic backend · inlining params in chat_controller.

---

## 9. Related docs

- [Project structure](./project-structure.md)
- [Pipeline / SSE](./m_agent_pipeline.md)
- [Chat API](./chat_api/README.md)
- [WorkspaceMem](F:/AI/WorkspaceMem)

**Maintenance:** update zh-CN and EN together; keep `src/m_agent/systems/README*.md` and `config/**/README.md` as short indexes only.
