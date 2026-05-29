# M-Agent

**M-Agent** is a **memory-centric** agent framework for **personal information life**.
![pipeline_img](docs/M-Agent.png)




## How to Run

### Server side (Chat API)

Run the agent as a **long-lived HTTP / SSE service** (`python -m m_agent.api.chat_api`). You create a run per user message, subscribe to the event stream, and read the final result while the server keeps **thread-level** session state.

Two **runtime profiles** are available (see `runtime.profile` in [`config/agents/chat/chat_controller.yaml`](config/agents/chat/chat_controller.yaml)):

| Profile | Purpose |
| --- | --- |
| **`legacy`** (default) | Single-turn-style chat loop: perception → thinking → execution → thinking summarizes the **answer** returned by the API. |
| **`think_life`** | Product runtime: stimuli go through a **perception bus**, **transaction-scoped WM**, chronological **Scene log**, and user-visible text only via the **`reply_to_user`** tool. Schedule heartbeat and execution feedback are integrated. Spec: **[docs/think-life-runtime-spec.zh-CN.md](docs/think-life-runtime-spec.zh-CN.md)**. |

Enable Think-life either in YAML (`runtime.profile: think_life`) or at startup with `--runtime-profile think_life` (CLI overrides YAML).

### Client side

- **M-Agent-UI**: the simplest information-interaction surface **[available now]**
- **M-Agent-desktop**: a desktop-form personal assistant

---

## Repository Layout

Core source code lives under `src/m_agent/`, runnable entry scripts under `scripts/`, automated tests under `tests/`, examples under `examples/`, and experimental integrations under `experiments/`. Configuration lives under `config/`, while runtime artifacts mostly land in `data/` and `log/`.

For a fuller directory layout and design conventions, see: **[docs/project-structure.md](docs/project-structure.md)**.

---

## Requirements

- **Python**: `>= 3.10` (see `pyproject.toml`)
- **Neo4j (optional)**: required when graph storage / entity-relation features are enabled (install separately and ensure connection settings match the project)
- **LLM / Embedding / Rerank**: configured via `.env` and YAML files under `config/`, supporting OpenAI-compatible providers, Alibaba Cloud (DashScope), etc. (see below)

---

## Installation

From the project root:

```powershell
# Windows PowerShell example
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Editable install (recommended for local development):

```bash
pip install -e .
```

---

## Environment Variables (`.env`)

Create a `.env` file in the project root and fill in keys / base URLs as needed. Common entries are listed below (defer to in-repo config comments for the source of truth):

```dotenv
# Chat / RAG LLM (e.g. src/m_agent/load_model/OpenAIcall.py)
# Fill in either API_SECRET_KEY or OPENAI_API_KEY
API_SECRET_KEY=YOUR_OPENAI_COMPATIBLE_KEY
OPENAI_API_KEY=
BASE_URL=https://api.openai.com/v1

# Chat model (config/agents/chat/chat_model.yaml)
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_KEY

# RAG embedding (config/systems/episodic/rag_default.yaml)
ALIBABA_API_KEY=YOUR_ALIBABA_KEY
ALIBABA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ALIBABA_EMBED_MODEL=text-embedding-v4
# Rerank: compatible-API example; for the Singapore region switch to dashscope-intl

# Optional switches (keep aligned with current repo defaults)
LANGUAGE=zh
EMBED_PROVIDER=aliyun
LLM_PROVIDER=deepseek
```

---

## Usage 1: Chat API as a Long-Running Backend (FastAPI)

The repo ships an HTTP / SSE chat service built on **fixed startup-time config + thread-level session state** (i.e. *not* the "send full config with every request" pattern).

### Legacy profile (default)

```powershell
$env:PYTHONPATH = "src"
python -m m_agent.api.chat_api `
  --host 127.0.0.1 `
  --port 8777 `
  --config config/agents/chat/chat_controller.yaml `
  --runtime-profile legacy `
  --idle-flush-seconds 1800 `
  --history-max-rounds 12 `
  --schedule-beat-seconds 10 `
  --schedule-busy-retry-seconds 5 `
  --users-db config/users/users.json `
  --session-ttl-seconds 43200
```

(`--runtime-profile legacy` is optional when `runtime.profile` in the YAML is already `legacy`.)

### Think-life profile

```powershell
$env:PYTHONPATH = "src"
python -m m_agent.api.chat_api `
  --host 127.0.0.1 `
  --port 8777 `
  --config config/agents/chat/chat_controller.yaml `
  --runtime-profile think_life `
  --idle-flush-seconds 1800 `
  --history-max-rounds 12 `
  --schedule-beat-seconds 10 `
  --schedule-busy-retry-seconds 5 `
  --users-db config/users/users.json `
  --session-ttl-seconds 43200
```

Or set `runtime.profile: think_life` in `chat_controller.yaml` and omit `--runtime-profile`.

Think-life tuning (delegates per transaction, Scene context window, preemption) lives under `runtime.think_life` in the same YAML file.

### After startup

- Swagger UI: `http://127.0.0.1:8777/docs`
- OpenAPI JSON: `http://127.0.0.1:8777/openapi.json`

Full API reference, authentication, thread events and schedule details: **[docs/chat_api/README.md](docs/chat_api/README.md)**.

### Bash (Linux / macOS)

```bash
export PYTHONPATH=src
python -m m_agent.api.chat_api \
  --host 127.0.0.1 \
  --port 8777 \
  --config config/agents/chat/chat_controller.yaml \
  --runtime-profile think_life
```



## Episodic memory in this repo (simple RAG)

The **chat stack** uses a lightweight **RAG episodic backend** (`SimpleRagEpisodicBackend`) configured via `config/systems/episodic/rag_default.yaml`. It chunks dialogue, embeds locally, and serves `shallow_recall` / `deep_recall` through the pluggable `systems` layer.

With **Think-life**, a separate **Scene log** (chronological, cross-transaction narrative) is stored under `data/memory/chat-api/<user>/scene/<thread_id>.jsonl`, alongside episodic RAG and dialogue archives.

## WorkspaceMem (full memory stack + benchmarks)

The evidence-driven **MemoryAgent / MemoryCore** implementation and **LoCoMo / LongMemEval / REALTALK** evaluation pipelines live in the sibling repository:

**[F:/AI/WorkspaceMem](F:/AI/WorkspaceMem)** (`workspace_mem` Python package)

Install and run eval from that repo; M-Agent intentionally does not vendor those scripts anymore.

- **[docs/project-structure.md](docs/project-structure.md)** — M-Agent layout
- **[src/m_agent/systems/README.md](src/m_agent/systems/README.md)** — plug-in contracts

---


## Tests

```bash
pytest
```

For markers and policy, see `[tool.pytest.ini_options]` in `pyproject.toml`.

---

## Documentation Index

| Document | Content |
| --- | --- |
| [docs/project-structure.md](docs/project-structure.md) | Directory conventions and common commands |
| [scripts/run_locomo/README.md](scripts/run_locomo/README.md) | LoCoMo configuration and per-script reference |
| [docs/chat_api/README.md](docs/chat_api/README.md) | Full Chat API reference |
| [docs/think-life-runtime-spec.zh-CN.md](docs/think-life-runtime-spec.zh-CN.md) | Think-life runtime spec (Chinese) |
| [tools/M-Agent-UI/API.md](tools/M-Agent-UI/API.md) | Frontend integration API |

---

## License

This project is released under the **MIT License**. See the root [LICENSE](LICENSE) file for details.

---

**中文 README:** [README-zh.md](README-zh.md)
