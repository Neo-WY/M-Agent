# 可插拔子系统开发指南（`m_agent.systems` + `config/systems`）

> 英文版：[systems-plugin-development.md](./systems-plugin-development.md)

本文档是 **对外开发者** 的唯一详细说明：如何在 M-Agent 对话栈中新增或替换 WM / 情景记忆 / 工具子系统，以及如何编写对应的 `config/systems/*.yaml`。

源码落点：`src/m_agent/systems/`。配置落点：`config/systems/`。顶层挂载：`config/agents/chat/chat_controller.yaml` 的 `systems:` 三行指针。

**不在本文范围：** 完整 MemoryAgent / MemoryCore / LoCoMo 评测 → [**WorkspaceMem**](F:/AI/WorkspaceMem)。

---

## 1. 边界与原则

| 原则 | 说明 |
|------|------|
| 插拔点唯一 | 可替换组件只通过 `m_agent.systems` 暴露；不要改 `layers/`、`chat/` 内部来“偷偷”接后端。 |
| 配置不内联 | `chat_controller.yaml` **只写** `systems.wm/episodic/tools` 的路径；参数全部在子系统 YAML。 |
| 骨架 vs 整合包 | 子系统根目录放 `protocols.py`、`system.py`、loader；具体实现放在 `<subsystem>/default/` 或你的 `<subsystem>/<包名>/`。 |
| 不动内置 default 做试验 | 私有实验用新子包 + 新 YAML；避免直接改 `default/` 导致合并冲突。 |
| Protocol 鸭子类型 | 实现类不必继承 Protocol；加载时用 `isinstance` + `@runtime_checkable` 校验。 |

---

## 2. 架构一览

### 2.1 概念

| 术语 | 含义 |
|------|------|
| **子系统** | `wm` / `episodic` / `tools` |
| **接入点** | 子系统 dataclass 内字段，如 `episodic.backend` |
| **整合包** | `episodic/default/`、`tools/default/capabilities/` 等一组实现 |
| **系统 YAML** | `config/systems/<子系统>/<变体>.yaml` |
| **Chat 指针** | `chat_controller.yaml` → 相对路径，相对 `config/agents/chat/` 解析 |

### 2.2 加载链路

```text
config/agents/chat/chat_controller.yaml
  systems:
    wm:       ../../systems/wm/default.yaml
    episodic: ../../systems/episodic/rag_default.yaml
    tools:    ../../systems/tools/default.yaml
        │
        ▼
load_systems_bundle_from_config()  →  SystemsBundle
        │
        ▼
ThreeLayerChatAgent
  ├─ ThinkingAgent  ← wm.reader/writer, episode recorder
  └─ ExecutionAgent ← wm.display + tools.registry + episodic.backend（经 capability）
```

### 2.3 源码目录

```text
src/m_agent/systems/
├── loader.py, bundles.py
├── wm/          protocols.py, system.py, default/
├── episodic/    protocols.py, system.py, query_module.py, default/
└── tools/       base.py, registry.py, system.py, default/
```

### 2.4 配置目录（当前仓库）

```text
config/
├── agents/chat/          chat_controller.yaml, chat_model.yaml, runtime/
├── agents/email|schedule/
├── systems/
│   ├── wm/default.yaml
│   ├── episodic/rag_default.yaml
│   └── tools/default.yaml, runtime_descriptions.yaml
├── prompts/examples/     示例（非对话栈必需）
├── integrations/         如 neo4j.yaml
└── users/                按用户生成；勿在仓库内手改他人目录
```

### 2.5 六个接入点

| 系统 | 字段 | 类型 | 内置默认 `path` |
|------|------|------|-----------------|
| `WMSystem` | `writer` | `WMWriter` | `wm.default.defaults:DefaultWMWriter` |
| `WMSystem` | `reader` | `WMReader` | `wm.default.defaults:DefaultWMReader` |
| `WMSystem` | `display` | `WMDisplay` | `wm.default.defaults:DefaultWMDisplay` |
| `EpisodicMemorySystem` | `recorder` | `EpisodeRecorder` | `episodic.default.recorder:DefaultEpisodeRecorder` |
| `EpisodicMemorySystem` | `backend` | `EpisodicMemoryBackend` | `episodic.default.rag_backend:SimpleRagEpisodicBackend` |
| `EpisodicMemorySystem` | `query_module` | `EpisodeQueryModule` | YAML `query:`（非 path） |
| `ToolSuiteSystem` | `registry` | `ControllerCapabilityRegistry` | `tools.default.registry:get_default_capability_registry` |

另：`ToolSuiteSystem` 还有策略字段 `enabled`、`defaults`、`runtime_descriptions`（均在 tools 系统 YAML 内配置）。

---

## 3. YAML 规范

### 3.1 通用规则

- 顶层必须有 `system: wm | episodic | tools`，与文件用途一致，否则 loader 报 `SystemsConfigError`。
- 插件槽位使用 **字符串 path** 或 **映射 `{ path, kwargs }`**。
- `path` 形式：`pkg.module:Symbol` 或 `pkg.module.Symbol`（最后一段为属性名）。
- Loader 调用：`Symbol(**kwargs)`；无参工厂则 `Symbol()`。
- **环境变量：** loader **不会** 展开 `${VAR}`；请在部署侧注入或写死测试值。

### 3.2 `config/agents/chat/chat_controller.yaml`

**应包含：**

```yaml
model_config_path: "./chat_model.yaml"
runtime_prompt_config_path: "./runtime/chat_controller_runtime.yaml"
email_agent_config_path: "../email/gmail_email_agent.yaml"
schedule_agent_config_path: "../schedule/schedule_agent.yaml"

systems:
  wm:       ../../systems/wm/default.yaml
  episodic: ../../systems/episodic/rag_default.yaml
  tools:    ../../systems/tools/default.yaml

execution:
  max_executions_per_turn: 1
  skip_summarize_on_direct_answer: true
```

**不应包含：** `enabled_tools`、`tool_defaults`、`working_memory`、`plugins` 等与 `systems/*` 重复的块（旧用户副本可保留，loader 仍兼容一个版本）。

**切换子系统：** 只改 `systems.<name>` 指向的另一份 YAML。

### 3.3 WM 系统 YAML（`system: wm`）

| 字段 | 必填 | 说明 |
|------|------|------|
| `writer` | 否 | 默认 `DefaultWMWriter`；可 `{ path, kwargs }` |
| `reader` | 否 | 默认 `DefaultWMReader`（注入思考层 plan/summarize） |
| `display` | 否 | 默认 `DefaultWMDisplay`（注入执行层 system prompt；默认与 reader 相同 tail-N） |
| `config` | 否 | `WorkingMemoryConfig` 字段（`enable`、`inject_max_entries`、`max_stored_entries` 等） |

Loader 对 `writer`/`reader`/`display` 自动注入 `default_kwargs={"config": <解析后的 config>}`。

参考：`config/systems/wm/default.yaml`。

### 3.4 Episodic 系统 YAML（`system: episodic`）

| 字段 | 必填 | 说明 |
|------|------|------|
| `recorder` | 否 | 默认 `DefaultEpisodeRecorder`；评测可换 `EpisodeRecorderNoop` |
| `backend` | 否 | 默认 `SimpleRagEpisodicBackend`；**必须** 满足 `EpisodicMemoryBackend` |
| `query.enabled` | 否 | 默认 `true`；为 `false` 时不应向 tools 暴露 recall（与 `enabled` 对齐） |
| `query.capability_names` | 否 | 可选，限制回忆类工具名列表 |

**`SimpleRagEpisodicBackend` 常用 kwargs：**

| kwargs | 含义 |
|--------|------|
| `storage_dir` | RAG 索引的「父目录」（与 `workflow_id` 拼成最终 `persistence_root`） |
| `workflow_id` | 在 `storage_dir` 下的子目录名（slug） |
| `top_k` | 检索条数（shallow/deep 共用） |
| `embed_model` | `hash`（离线/测试）、`alibaba`、`bge` |

参考：`config/systems/episodic/rag_default.yaml`。

> **Chat API 运行时覆盖：** `ThreeLayerChatAgent` 在组装 `SystemsBundle` 后会调用 `_rebind_episodic_for_chat_user()`，把默认 RAG 指到**当前登录用户**目录（见下文 §3.4.1）。YAML 里的 `storage_dir: data/rag/chat` + `workflow_id: default` 主要给单测或未走 Chat 栈的脚本用。

#### 3.4.1 Chat 用户级持久化路径（对话归档 + 情景 RAG）

Chat 栈**不**再依赖已移除的 `m_agent.memory` / MemoryCore 管线；情景记忆默认是 **本地 RAG**（`SimpleRagEpisodicBackend`），与 **对话 JSON 归档** 分工如下：

| 存储 | 路径（用户 `chat_user_name=test`） | 何时写入 | 用途 |
|------|-----------------------------------|----------|------|
| 对话归档 | `data/memory/chat-api/test/dialogues/YYYY-MM/*.json` | `POST .../memory/flush` 成功时（`ChatDialogueArchive`） | `GET /v1/chat/dialogues`、审计、回放 |
| 情景 RAG | `data/memory/chat-api/test/episodic/{chunks.jsonl, embeddings.npy}` | 每轮 `persist_round` + flush 时 `persist_dialogue` | `shallow_recall` / `deep_recall` 检索 |
| 工作记忆 WM | 进程内 `ConversationState.wm_entries`（不落盘） | 每轮执行后 `WMWriter` 投影 tool_history | `WMReader` → 思考层；`WMDisplay` → 执行层（默认均为近期 tail-N） |

路径由 `m_agent.paths` 统一解析（可用环境变量改根目录）：

```text
M_AGENT_MEMORY_ROOT 或 M_AGENT_DATA_DIR/memory 或 <项目>/data/memory
  └── chat-api/<user_slug>/
        ├── dialogues/
        └── episodic/
```

辅助函数：

- `chat_memory_workflow_id(user_name)` → `"chat-api/test"`
- `chat_user_persistence_root(user_name)` → 用户根目录
- `chat_user_dialogues_dir(user_name)` → `.../dialogues`
- `chat_user_episodic_rag_paths(user_name)` → `(storage_dir, workflow_id="episodic", index_root)`

**实现类暴露：** `SimpleRagEpisodicBackend.persistence_root`、`describe_persistence()`（含 `chunks_path`、`embeddings_path`、`chunk_count`）。`ThreeLayerChatAgent.describe_episodic_persistence()` 汇总对话目录 + RAG 路径。

**HTTP：** `GET /v1/chat/threads/{id}/memory/state` 的 `thread_state.episodic_persistence` 字段可用来调试路径与 chunk 数量。

**历史数据迁移：** `POST /v1/chat/dialogues/import`（`migrate_legacy: true`）可将旧布局 `data/memory/user_<username>/dialogues/` 复制到 `chat-api/<slug>/dialogues/` 并重建 RAG；实现见 `m_agent.chat.dialogue_import`。

**注意：**

- 只写 `dialogues/*.json` **不会**自动建 embedding；必须经 `backend.persist_round` / `persist_dialogue` 或手动灌库。
- 自定义 `EpisodicMemoryBackend` 若需对齐 Chat 目录，应在构造时读 `chat_user_episodic_rag_paths(chat_user_name)`，或实现 `describe_persistence()` 供 UI 展示。

### 3.5 Tools 系统 YAML（`system: tools`）

| 字段 | 必填 | 说明 |
|------|------|------|
| `registry` | 否 | 默认进程级 default registry；第三方应指向 `build_my_registry` 工厂 |
| `enabled` | 否 | 工具名白名单；缺省为 registry 内默认顺序 ∩ 已注册名 |
| `defaults` | 否 | 每工具参数字典；`__controller__.max_calls_per_turn` 为整轮上限 |
| `defaults.memory_recall.max_calls_per_turn` | 否 | shallow+deep 组上限 |
| `runtime_descriptions` | 否 | 内联描述（字符串或 `{zh, en}`） |
| `runtime_descriptions_path` | 否 | 相对 **本 YAML 文件** 的路径；见 `runtime_descriptions.yaml` |

工具描述优先级：`systems.tools.runtime_descriptions` > `chat_controller_runtime.yaml` 内 legacy `tools.<name>.description`（兜底）。

参考：`config/systems/tools/default.yaml`、`runtime_descriptions.yaml`。

---

## 4. 交付新整合包（强制流程）

1. 选定子系统：`wm` | `episodic` | `tools`（一个 YAML 文件只对应一个）。
2. 阅读对应 `protocols.py` / `base.py`，实现全部必需方法。
3. **代码位置**
   - 仓库内：`src/m_agent/systems/<子系统>/<包名>/`（与 `default` 同级）。
   - 仓库外：独立 pip 包；确保运行环境能 `import` YAML 中的模块。
4. 在包 `__init__.py` 导出 YAML 会引用的类/工厂。
5. 复制最接近的 `config/systems/<子系统>/*.yaml` → `my_variant.yaml`，改 `path`/`kwargs`。
6. 在 `chat_controller.yaml` 的 `systems:` 中指向新 YAML。
7. **测试**（见第 7 节）通过后提 PR。
8. 更新本仓库文档仅当新增**官方**变体（可选）。

---

## 5. 子系统实现要求

### 5.1 WM

**职责**

- `WMWriter.write(entries, tool_history)`：原地追加 WM 条目并遵守 `max_stored_entries`。
- `WMReader.render(entries, *, language)`：生成注入思考层 plan/summarize 的文本。
- `WMDisplay.render(entries, *, language)`：生成注入执行层 system prompt 的文本（默认与 reader 相同 tail-N）。

**禁止：** 在 WM 包内直接调用 episodic 或 Email/Schedule。

**示例 YAML：** 见第 3.3 节；语义 Reader 示例见英文版或 `wm/default/defaults.py`。

### 5.2 Episodic

**数据流**

```text
ThinkingAgent → episode_note → recorder.append(buffer)
ExecutionAgent → shallow_recall / deep_recall → backend
每轮 chat 结束 → backend.persist_round(...)     # 追加 RAG chunk（用户目录下 episodic/）
Flush 成功 → ChatDialogueArchive.persist_dialogue   # 写 dialogues/*.json
          → backend.persist_dialogue(...)           # 批量追加 RAG chunk
          → thinking.on_flush → backend.on_flush(episode_notes=...)  # 默认 RAG 合并 notes 到最后 chunk
```

**与 WM 的边界：** WM 是「本轮工具调用摘要」，进程内、给思考层读；**情景 RAG** 是跨轮持久检索，路径见 §3.4.1。二者不要混在同一存储里实现。

**`EpisodicMemoryBackend`（五个方法，均需实现）**

```python
def shallow_recall(self, question: str, *, thread_id: str) -> dict: ...
def deep_recall(self, question: str, *, thread_id: str) -> dict: ...
def persist_round(self, *, thread_id: str, user_message: str,
                  assistant_message: str, agent_result: dict | None = None) -> dict: ...
def persist_dialogue(self, *, thread_id: str, rounds: list[dict],
                     reason: str, source: str, progress_callback=None) -> dict: ...
def on_flush(self, *, thread_id: str, conversation_id: str,
             episode_notes: list[dict]) -> None: ...
```

回忆返回值至少应含 `answer`（`tools/default/capabilities/recall.py` 会记录 trace）。

**`EpisodeRecorder`**

```python
def append(self, buffer: list[dict], *, note: str | None, turn_meta: dict) -> None: ...
def flush(self, buffer: list[dict], *, thread_id: str, conversation_id: str) -> None: ...
```

参考实现：`episodic/default/recorder.py`、`rag_backend.py`、`rag_store.py`。

### 5.3 Tools

**职责**

- 每个 capability 是一个 `ControllerCapabilitySpec(name=..., build_tool=...)`。
- `build_tool(context, description)` 返回 LangChain `@tool`；必须走 `context.start_tool_call` / `finish_tool_call` / `check_tool_call_limits`。
- 回忆类工具 **必须** 使用 `context.get_episodic_backend()`，不得自建存储。

**扩展方式**

| 方式 | 适用 |
|------|------|
| A. 改 `tools/default/` | 扩展官方工具集（改 registry 列表 + default.yaml `enabled`） |
| B. 新包 + `build_*_registry()` | 第三方/隔离部署（推荐） |

**禁止：** 在库代码里调用 `register_capability()` 污染全局 default registry（仅进程内单例场景慎用）。

邮件/日程：通过 `context.email_agent_provider()` / `schedule_agent_provider()` 懒加载领域 Agent。

参考：`tools/default/capabilities/recall.py`、`email_ops.py`。

---

## 6. 运行时覆盖与优先级

`ThreeLayerChatAgent` 解析顺序（单槽可独立覆盖）：

1. 构造参数 `systems=SystemsBundle(...)`
2. 旧 `plugins=`（`DeprecationWarning`）
3. YAML `systems:`
4. 旧 YAML `plugins:` / 扁平 legacy 字段
5. 代码内置 default

**测试 / API 注入：**

```python
from m_agent.systems import SystemsBundle, load_episodic_system

bundle = SystemsBundle(
    episodic=load_episodic_system({"system": "episodic", "backend": {"path": "..."}}),
)
```

---

## 7. 测试与验收标准

### 7.1 必跑

```bash
pytest tests/systems/
pytest tests/chat/test_three_layer_plugins.py
```

### 7.2 推荐用例

| 目标 | 文件 |
|------|------|
| Protocol 形状 | `tests/systems/test_protocol_shapes.py` |
| 磁盘 YAML 可加载 | `tests/systems/test_system_yaml_loader.py` |
| RAG backend | `tests/systems/episodic/test_rag_backend.py` |
| `systems_override` | `tests/systems/test_runtime_systems_override.py` |
| 工具调用上限 | `tests/test_chat_controller_tool_limits.py` |

### 7.3 新 backend 最小单测

```python
from m_agent.systems.episodic.protocols import EpisodicMemoryBackend

def test_my_backend_is_protocol():
    assert isinstance(MyBackend(storage_dir=":memory:"), EpisodicMemoryBackend)
```

### 7.4 PR 自检清单

- [ ] 新 `path` 在目标 venv 可 `import`
- [ ] `kwargs` 与构造函数一致
- [ ] `isinstance(..., Protocol)` 通过
- [ ] 已添加/更新 `config/systems/.../my_variant.yaml`
- [ ] `query.enabled` 与 `tools.enabled` 中的 recall 工具一致
- [ ] 未修改 `default/` 除非明确要改官方行为
- [ ] `pytest tests/systems/` 通过

---

## 8. 对话栈消费关系

| 模块 | 使用 |
|------|------|
| `ThreeLayerChatAgent` | 组装 `SystemsBundle`；`persist_round` / `on_flush` |
| `ThinkingAgent` | WM；recorder；**不**直接 recall |
| `ExecutionAgent` | tools → LangChain；recall 仅经 capability → backend |

领域 Agent（`EmailAgent`、`ScheduleAgent`）仍在 `m_agent.agents`；仅通过 tools capability 适配器接入。

---

## 9. 常见错误

1. **path 拼写错误** — 启动即 `SystemsConfigError`，而非首条聊天失败。
2. **kwargs 不匹配 `__init__`** — 同上。
3. **关闭 query 却启用 shallow_recall** — 配置不一致。
4. **全局 `register_capability`** — 多租户/多配置互相污染。
5. **Capability 绕过 backend 读记忆** — 无法通过换 episodic YAML 切换实现。
6. **在 chat_controller 内联子系统参数** — 违反单一配置源，难维护。

---

## 10. Legacy 兼容（一个版本）

以下字段若仍出现在 **旧** `config/users/*/chat.yaml` 中，loader 会翻译为虚拟 `SystemsBundle`（可能伴随 `DeprecationWarning`）：

- `plugins:`
- `enabled_tools` / `tool_defaults`
- `working_memory`
- `episode_query_enabled`

新模板 `config/agents/chat/chat_controller.yaml` 已仅使用 `systems:`。新用户脚手架会复制该模板。

---

## 11. 相关文档

- [项目结构](./project-structure.md)
- [对话流水线与 SSE](./m_agent_pipeline.md)
- [Chat API](./chat_api/README.md)
- [WorkspaceMem](F:/AI/WorkspaceMem) — MemoryAgent 与评测

维护说明：扩展本指南时，请同步更新英文版 `systems-plugin-development.md`；`src/m_agent/systems/README*.md` 与 `config/**/README.md` 仅保留短索引指向本文。
