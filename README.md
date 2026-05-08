# M-Agent

**M-Agent** is a **memory-centric** agent framework for **personal information life**.
![pipeline_img](docs/M-Agent.png)




## How to Run
### Server side
- **Run the agent as a service (FastAPI + SSE)**: create a run, subscribe to its event stream, fetch the final result, and maintain thread-level conversation state.
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
# MemoryCore LLM (e.g. src/m_agent/load_model/OpenAIcall.py)
# Fill in either API_SECRET_KEY or OPENAI_API_KEY
API_SECRET_KEY=YOUR_OPENAI_COMPATIBLE_KEY
OPENAI_API_KEY=
BASE_URL=https://api.openai.com/v1

# Agent model (LoCoMo defaults may point to gpt-4o-mini etc.;
# MemoryAgent will map keys to the OPENAI_* variables LangChain expects)
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_KEY

# Embedding (embed_provider, see config/memory/core/*.yaml)
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

Startup example (PowerShell):

```powershell
$env:PYTHONPATH = "src"
python -m m_agent.api.chat_api `
  --host 127.0.0.1 `
  --port 8777 `
  --config config/agents/chat/chat_controller.yaml `
  --idle-flush-seconds 1800 `
  --history-max-rounds 12 `
  --schedule-beat-seconds 10 `
  --schedule-busy-retry-seconds 5 `
  --users-db config/users/users.json `
  --session-ttl-seconds 43200
```

Once running:

- Swagger UI: `http://127.0.0.1:8777/docs`
- OpenAPI JSON: `http://127.0.0.1:8777/openapi.json`

Full API reference, authentication, thread events and schedule details: **[docs/chat_api/README.md](docs/chat_api/README.md)**.



## Episodic Memory System (Workspace-Mem)

**Workspace-Mem** is an in-house, evidence-driven memory system. It supports **memory reasoning at varying intensities** and **fusion of evidence from heterogeneous sources**, allowing the agent to operate over multiple memory stores with different origins and structures simultaneously. With precise recall and analysis over episodic information, it can handle the kind of intricate, entity-level questions that arise in real-world scenarios.

![pipeline_img](docs/pipeline_img_zh.png)
**Figure 1.** Overview of the Workspace-Mem retrieval framework. *(figure currently labeled in Chinese; an English version is on the way)*

The memory system is still under active development. The current implementation already shows competitive performance on the pure-episodic benchmark **LoCoMo**:

![LOCOMO_eval_img](docs/LOCOMO_eval_zh.png)
**Figure 2.** Side-by-side comparison of Workspace-Mem on LoCoMo. *(figure currently labeled in Chinese; an English version is on the way)*

Benchmarks and results in more complex input / understanding settings will be released soon — stay tuned.

For implementation details and engineering conventions (e.g. how `episodes → scene → atomic facts` are generated, and how data directories are organized), start here:

- **[scripts/run_locomo/README.md](scripts/run_locomo/README.md)** (config-driven workflow and data directory layout)
- **[docs/project-structure.md](docs/project-structure.md)** (code / scripts / path conventions)

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
| [tools/M-Agent-UI/API.md](tools/M-Agent-UI/API.md) | Frontend integration API |

---

## License

This project is released under the **MIT License**. See the root [LICENSE](LICENSE) file for details.

---

**中文 README:** [README-zh.md](README-zh.md)
