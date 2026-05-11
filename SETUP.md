# Project Setup Guide

This guide explains how to get the project running from scratch, independently of any other project on your machine.

---

## What is a Virtual Environment?

When you install Python packages (like `gradio`, `anthropic`, etc.), they get stored somewhere on your computer. The problem: if two projects need different versions of the same package, they will conflict.

A **virtual environment** is an isolated folder that holds packages for *one specific project only*. It is completely separate from other projects and from your system Python.

```
Your Mac
├── System Python (don't touch this)
├── projects/
│   ├── full-llm-assistant/
│   │   ├── .venv/           ← packages ONLY for this project
│   │   ├── main.py
│   │   └── ...
│   └── some-other-project/
│       ├── .venv/           ← completely separate packages
│       └── ...
```

---

## One-Time Setup (do this once)

Open a terminal and run these commands **in order**:

### Step 1 — Go to the project folder

```bash
cd /Users/sobhandutta/projects/full-llm-assistant
```

### Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
```

This creates a `.venv` folder inside the project. It contains its own Python and pip, totally isolated from everything else.

### Step 3 — Activate the virtual environment

```bash
source .venv/bin/activate
```

Your terminal prompt will change to show `(.venv)` at the start — that tells you the environment is active:

```
(.venv) sobhandutta@Sobhans-MacBook-Pro full-llm-assistant %
```

**Important:** every time you open a new terminal to work on this project, you must run this activate command again. The environment does not stay active between terminal sessions.

### Step 4 — Install dependencies

```bash
pip install -r requirements.txt
pip install openai chromadb
```

> `openai` is needed for embeddings (the RAG vector search feature).
> `chromadb` is needed to store and search those embeddings.
> Both are used by the project but were missing from `requirements.txt`.

### Step 5 — Add your API keys

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` in your editor and set:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Both keys are required — Anthropic runs the chat, OpenAI runs the embeddings.

### Step 6 — Seed the database

```bash
python data/seed_db.py
```

This creates `data/personal.db` — the SQLite database the assistant reads from.
Edit `data/seed_db.py` first if you want to put your own information in it.

### Step 7 — Build the vector store

```bash
python data/ingest_kb.py
```

This reads all the Markdown files in `knowledge_base/`, splits them into chunks, and stores them in `vector_store/` so the RAG agent can search them.

### Step 8 — Run the app

```bash
python main.py
```

Open your browser at **http://127.0.0.1:7860**

---

## Every Day After That

You only need Steps 1–8 once. After the first time, the daily workflow is:

```bash
# 1. Go to the project
cd /Users/sobhandutta/projects/full-llm-assistant

# 2. Activate the environment
source .venv/bin/activate

# 3. Run the app
python main.py
```

---

## How to Deactivate

When you are done and want to leave the virtual environment:

```bash
deactivate
```

Your prompt goes back to normal. Your packages are still there — they are just not "active" until you run `source .venv/bin/activate` again.

---

## Troubleshooting

### "ModuleNotFoundError: No module named X"

You are running Python without the virtual environment active. Fix:

```bash
source .venv/bin/activate
python main.py
```

### "python3: No module named pip"

Your system Python does not have pip. Use the venv's pip directly:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install openai chromadb
```

### Check which Python is active

```bash
which python
```

It should show a path ending in `.venv/bin/python`. If it shows something else, you forgot to activate.

---

## Summary

| Command | What it does | When to run |
|---|---|---|
| `python3 -m venv .venv` | Creates the isolated environment | Once |
| `source .venv/bin/activate` | Activates it for this terminal session | Every new terminal |
| `pip install -r requirements.txt` | Installs packages | Once (or after adding new packages) |
| `pip install openai chromadb` | Installs missing packages | Once |
| `python data/seed_db.py` | Creates your personal database | Once (or to refresh data) |
| `python data/ingest_kb.py` | Builds the RAG vector store | Once (or after editing knowledge_base/) |
| `python main.py` | Starts the app | Every time you want to use it |
| `deactivate` | Leaves the virtual environment | When done |
