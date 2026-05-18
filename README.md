---
title: Ask About Sobhan
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# agentic-personal-assistant

A personal AI assistant that answers questions about *you* by orchestrating five specialist sub-agents, each reading from a different data source. Built from scratch in Python — no heavy frameworks, no magic — so every concept is visible and understandable.

## Quick Start

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install openai chromadb
cp .env.example .env          # fill in ANTHROPIC_API_KEY + OPENAI_API_KEY
python data/seed_db.py        # create your personal database
python data/ingest_kb.py      # build the RAG vector store

# Run
python main.py                # opens at http://127.0.0.1:7860
uvicorn api:app --host 0.0.0.0 --port 8000 --reload #open http://localhost:8000
```

Every new terminal: `source .venv/bin/activate` before `python main.py`.

See [GUIDE.md](GUIDE.md) for full setup details, architecture walkthrough, and concept explanations.
