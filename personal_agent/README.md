# Personal Agent – Unbeatable AI Assistant

This repository implements a **self‑hosted, extensible personal AI assistant** that:

- Reasons with the Gemini‑3.8 model (or later).
- Uses **retrieval‑augmented generation** (RAG) to stay up‑to‑date.
- Executes safe PowerShell, file‑system, and web‑request tools inside a sandbox.
- Persists long‑term memory in SQLite.
- Enforces safety guards against jailbreaks.
- Emits OpenTelemetry traces for observability.

## Quick Start (Windows)
```powershell
# 1️⃣ Clone (or copy) the repo into your workspace
# 2️⃣ Create a virtual environment and install deps
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3️⃣ Index your personal documents (default: ~/Downloads)
python -m rag.indexer

# 4️⃣ Run the REPL
python -m agent.repl
```

The REPL will accept natural‑language commands, decide if a tool is required, and return the result.

## Project Layout
```
personal_agent/
├─ agent/          # Core orchestration (LLM wrapper, planner, REPL)
├─ plugins/        # Tool plugins (PowerShell, File, Web)
├─ rag/            # Vector store and search utilities
├─ memory/         # SQLite‑backed personal facts
├─ safety/         # Guardrails and red‑team tests
├─ otel/           # OpenTelemetry instrumentation
├─ tests/          # Unit / integration tests
├─ docs/           # Design docs and cheat‑sheets
├─ data/           # Persistent RAG DB, SQLite DB, backups
└─ logs/           # Runtime logs & trace files
```

For full documentation, see the `docs/` folder.

---

**License**: MIT – feel free to fork and improve!
