# Personal AI Assistant — Architecture Guide & Learning Tutorial

> **What this is:** A personal AI assistant that answers questions about *you* by orchestrating
> five specialist sub-agents, each reading from a different data source. Built from scratch in
> Python — no heavy frameworks, no magic — so every concept is visible and understandable.

---

## Steps to run the application

```bash
# 1. Create and activate a virtual environment (one time only)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (one time only)
pip install -r requirements.txt
pip install openai chromadb

# 3. Add your API keys (one time only)
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY and OPENAI_API_KEY

# 4. Seed the database (one time only)
python data/seed_db.py

# 5. Build the RAG vector store (one time only, or after editing knowledge_base/)
python data/ingest_kb.py

# 6. Run the app
python main.py
```

> Every new terminal session: run `source .venv/bin/activate` before `python main.py`.


## Table of Contents

1. [The Big Idea — What is Agentic AI?](#1-the-big-idea)
2. [Architecture — How the Pieces Fit Together](#2-architecture)
3. [Mental Model — Think of it Like a Manager and Team](#3-mental-model)
4. [File Structure — Where Everything Lives](#4-file-structure)
5. [Tech Stack — What We Use and Why](#5-tech-stack)
6. [Key Concept: Tool Calling](#6-key-concept-tool-calling)
7. [Key Concept: The Tool-Calling Loop](#7-key-concept-the-tool-calling-loop)
8. [Key Concept: Parallel Dispatch](#8-key-concept-parallel-dispatch)
9. [Key Concept: Short-Term Memory](#9-key-concept-short-term-memory)
10. [Key Concept: RAG (Retrieval-Augmented Generation)](#10-key-concept-rag)
11. [Key Concept: Multi-Provider Support](#11-key-concept-multi-provider-support)
12. [Key Files — Annotated Walkthroughs](#12-key-files-annotated-walkthroughs)
13. [Step-by-Step: How to Run It](#13-how-to-run-it)
14. [Step-by-Step: Enable Google Drive + Gmail](#14-enable-google-drive--gmail)
15. [Demo Queries to Try](#15-demo-queries-to-try)
16. [Cost Strategy](#16-cost-strategy)
17. [What to Study Next](#17-what-to-study-next)

---

## 1. The Big Idea

### What is "Agentic" AI?

A regular LLM call looks like this:

```
You → [question] → Claude → [answer]
```

An **agentic** system looks like this:

```
You → [question] → Claude → [hmm, I need data] → calls a tool
                          ← [tool returns data]
                          → [now I can answer] → [final answer] → You
```

The key insight is: **the LLM is not just generating text — it is making decisions about what
actions to take.** Claude decides *which* tools to call, *what* to ask them, and *how* to combine
their results into a coherent answer. You (the developer) just define the tools and execute them
when asked.

### What patterns does this project demonstrate?

| Pattern | Where you see it |
|---|---|
| Tool / function calling | Orchestrator calling sub-agents |
| Multi-agent orchestration | 5 agents, each with a different data source |
| Parallel tool dispatch | Multiple agents called simultaneously |
| NL → SQL translation | SQLiteAgent converting questions into SQL |
| Chained LLM calls | GmailAgent: query generation → email fetch → answer |
| Short-term memory | Conversation history injected into every call |
| RAG (Retrieval-Augmented Generation) | KnowledgeBaseAgent using vector search |
| Graceful degradation | Drive/Gmail agents fail safely when not authenticated |
| OAuth2 | Google authentication for real-world APIs |
| Multi-provider LLM | Switch between Anthropic, OpenAI, or Ollama via one config line |

---

## 2. Architecture

Here is the full data flow from user question to final answer:

```
┌─────────────────────────────────────────────────────────────────────┐
│                            USER                                     │
│   "What is my design philosophy and do I have any new job emails?"  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GRADIO UI  (main.py)                            │
│  Displays the chat. Passes user message + chat history              │
│  to the orchestrator. Shows the final answer.                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR  (orchestrator.py)                     │
│                                                                     │
│  1. Converts Gradio history → Anthropic message format (memory)    │
│  2. Calls LLM (sonnet / gpt-4o-mini / llama3.2) with tool defs     │
│  3. LLM responds: "I'll call query_knowledge_base AND query_gmail"  │
│  4. Orchestrator dispatches both tools IN PARALLEL                  │
│  5. Feeds results back to LLM                                       │
│  6. LLM writes the final answer                                     │
└──────┬───────────────────────────────────────────┬──────────────────┘
       │ (parallel)                                │ (parallel)
       ▼                                           ▼
┌──────────────────────────┐          ┌────────────────────────────┐
│  KnowledgeBaseAgent      │          │  GmailAgent                │
│                          │          │                            │
│  RAG Pipeline:           │          │  Call 1 (Claude haiku):    │
│  1. Embed question       │          │  NL → Gmail search query   │
│  2. Search ChromaDB      │          │  Gmail API: fetch emails   │
│  3. Claude reads chunks  │          │  Call 2 (Claude haiku):    │
│  4. Returns answer       │          │  Answer from email content │
└──────────────────────────┘          └────────────────────────────┘

  (SQLiteAgent, PortfolioAgent, DriveAgent sit alongside
   these — called in parallel when the question needs them)

┌─────────────────────────────────────────────────────────────────────┐
│                   MEMORY LAYER  (memory/)                           │
│  ConversationMemory trims chat history to the last N turns and      │
│  injects it into every orchestrator call so follow-up questions     │
│  ("tell me more about that") work correctly.                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mental Model

**Think of the orchestrator as a manager, and the sub-agents as specialist team members.**

- The **manager** (orchestrator) reads the user's question and decides who to ask.
- The **team members** (sub-agents) are experts in exactly one thing — they don't know about
  each other, they just answer what they're asked.
- The **manager** collects all the answers and writes the final coherent response.

The manager doesn't have the data. The team members don't have the reasoning. Together they do.

> A sub-agent is just a Python function that takes a question string and returns a string.
> The "agentic" part is the LLM deciding *which* function to call and *what* to pass to it.

### The five specialists and what they know

| Agent | Data Source | How it retrieves |
|---|---|---|
| `SQLiteAgent` | Personal SQLite database | NL → SQL → query |
| `PortfolioAgent` | Live portfolio website | HTTP scrape → Claude reads |
| `DriveAgent` | Google Drive documents | Drive API → Claude reads |
| `GmailAgent` | Gmail inbox | NL → Gmail query → fetch → Claude reads |
| `KnowledgeBaseAgent` | Pre-indexed markdown docs (RAG) | Embed → vector search → Claude reads |

---

## 4. File Structure

```
sobhan-projects/agentic/
│
├── main.py                      ← START HERE to run the app (Gradio UI)
├── orchestrator.py              ← The brain — tool-calling loop + provider routing
├── config.py                    ← All settings: models, provider, paths, limits
├── GUIDE.md                     ← This file
│
├── agents/                      ← One file per data source
│   ├── base_agent.py            ← Abstract class: all agents implement run(question) → str
│   ├── sqlite_agent.py          ← NL→SQL→result from personal SQLite database
│   ├── portfolio_agent.py       ← Scrapes live portfolio website, Claude answers
│   ├── drive_agent.py           ← Reads Google Drive documents
│   ├── gmail_agent.py           ← Searches Gmail inbox (2 chained LLM calls)
│   └── knowledge_base_agent.py  ← RAG: semantic search over knowledge_base/ docs
│
├── tools/
│   └── definitions.py           ← Tool schemas for all 5 agents (Anthropic + OpenAI format)
│
├── memory/
│   └── conversation.py          ← Converts Gradio history into API message format
│
├── knowledge_base/              ← Markdown documents indexed by the RAG agent
│   ├── career/                  ← ataya.md, elisity.md, nuance.md, early_career.md
│   ├── expertise/               ← ux_design_philosophy.md, frontend_engineering.md, leadership.md
│   └── education/               ← background.md
│
├── vector_store/                ← ChromaDB files (auto-generated by ingest_kb.py, gitignored)
│
├── data/
│   ├── seed_db.py               ← Run once to create + fill personal.db with your data
│   ├── personal.db              ← Your SQLite database (auto-created by seed_db.py)
│   └── ingest_kb.py             ← Run once to build the RAG vector store from knowledge_base/
│
├── auth/
│   ├── google_auth.py           ← Google OAuth2 helper (Drive + Gmail)
│   └── credentials/             ← Put client_secret.json here; token.json saved here
│
├── .env                         ← Your API keys (never commit this)
└── .gitignore                   ← Protects .env, token.json, personal.db, vector_store/
```

**Recommended reading order for learning:**
`config.py` → `tools/definitions.py` → `agents/base_agent.py` → `agents/sqlite_agent.py`
→ `agents/knowledge_base_agent.py` → `memory/conversation.py` → `orchestrator.py` → `main.py`

---

## 5. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestrator LLM | `claude-sonnet-4-6` (default) | Best reasoning + native tool calling |
| Sub-agent LLM | `claude-haiku-4-5` | 10× cheaper than Sonnet for simple tasks |
| Alternative providers | OpenAI `gpt-4o-mini`, Ollama `llama3.2` | Switch with one line in config.py |
| Orchestration | Raw Python + SDK | No LangChain magic — every line is visible |
| Database | SQLite (stdlib) | Zero setup. Open `personal.db` with DB Browser to inspect |
| Vector store | ChromaDB | Lightweight, local, no server needed — perfect for learning RAG |
| Embeddings | OpenAI `text-embedding-3-small` | Fast, cheap, high quality for semantic search |
| Google APIs | `google-api-python-client` | Official Google library — same as production apps use |
| UI | Gradio `ChatInterface` | 10 lines of code for a full chat UI |
| Memory | In-memory Python list | Simple and transparent — no Redis needed for short-term context |
| Parallelism | `ThreadPoolExecutor` | Runs multiple agents at the same time |

---

## 6. Key Concept: Tool Calling

This is the most important concept in the project. Everything else builds on it.

### What it is

When you call an LLM with `tools=TOOL_DEFINITIONS`, you give it a menu of actions it can take.
The LLM reads your question, looks at the menu, and decides what to order.

### How you define a tool

```python
{
    "name": "query_sqlite",           # The function name the LLM will call

    "description": "Query Sobhan's personal database...",
    # ↑ This is the most important field.
    #   The LLM reads this to decide WHEN to use this tool.
    #   Write it like a precise job description.

    "input_schema": {                 # What arguments does the tool take?
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural language question"
            }
        },
        "required": ["question"]
    }
}
```

**Lesson:** If your agent isn't being called, the description is too vague. If the wrong
agent is called, descriptions overlap too much. The description is the LLM's only guide.

### What the LLM returns when it wants to use a tool

```python
# Anthropic format:
response.stop_reason  # → "tool_use"

response.content      # → list of blocks:
# [
#   TextBlock(text="I'll check your database."),
#   ToolUseBlock(id="toolu_01abc", name="query_sqlite",
#                input={"question": "What companies has Sobhan worked at?"})
# ]

# OpenAI/Ollama format:
choice.finish_reason  # → "tool_calls"

choice.message.tool_calls  # → list of tool call objects
```

Your job as the developer: **execute the tool and feed the result back.**

---

## 7. Key Concept: The Tool-Calling Loop

This loop runs inside `orchestrator.py` until the LLM says it is done.

```
messages = [history] + [user message]
          │
          ▼
  ┌───────────────┐
  │   Call LLM    │◄──────────────────────┐
  └───────┬───────┘                       │
          │                               │
    ┌─────┴──────┐                        │
    │            │                        │
  "end_turn"  "tool_use"                  │
    │            │                        │
    ▼            ▼                        │
  Return    Execute tools            Append results
  answer    (in parallel)            to messages ──┘
  to user         │                  (loop again)
                  │
           Append Claude's
           tool-use message
           to messages
```

In code:

```python
while True:
    response = client.messages.create(model=..., messages=messages, tools=...)

    if response.stop_reason == "end_turn":
        return response.content[0].text          # Done!

    if response.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": response.content})
        results = run_tools_parallel(response.content)
        messages.append({"role": "user", "content": results})
        # loop continues — Claude will now read the results
```

**Why a loop?** Claude might call tools more than once. For example, it calls `query_sqlite`,
reads the result, then decides it also needs `query_knowledge_base`. Each round-trip is one
loop iteration.

---

## 8. Key Concept: Parallel Dispatch

When the LLM requests two or more tools at once, we run them **concurrently** using
`ThreadPoolExecutor`, not one after another.

```python
# SLOW — sequential (2 tools × 2s each = 4s total)
for tool_call in calls:
    result = agent.run(tool_call.input)

# FAST — parallel (2 tools × 2s each = 2s total — limited by the slowest)
with ThreadPoolExecutor(max_workers=len(calls)) as executor:
    futures = {
        executor.submit(self._dispatch, name, input_dict): call_id
        for call_id, name, input_dict in calls
    }
    for future in as_completed(futures):
        call_id = futures[future]
        results[call_id] = future.result()
```

**Real-world impact:** If SQLiteAgent takes 1s and GmailAgent takes 3s:
- Sequential: 4s total
- Parallel: 3s total (limited by the slowest)

With 5 agents all called simultaneously, the savings are even more significant.

---

## 9. Key Concept: Short-Term Memory

The LLM API is **stateless** — each call knows nothing about previous calls. To make follow-up
questions work ("tell me more about that"), you must send the full conversation history with
every request.

Gradio tracks history as `[[user_msg, assistant_msg], ...]`. The `ConversationMemory` class
converts this into the API format:

```python
# Gradio format (what Gradio gives you):
history = [
    ["What are my skills?",       "You have Python, UX design..."],
    ["Tell me more about Python", "You've used it for 6 years..."],
]

# Anthropic/OpenAI format (what the LLM needs):
messages = [
    {"role": "user",      "content": "What are my skills?"},
    {"role": "assistant", "content": "You have Python, UX design..."},
    {"role": "user",      "content": "Tell me more about Python"},
    {"role": "assistant", "content": "You've used it for 6 years..."},
    # ← new user message appended here
]
```

We trim to `MAX_MEMORY_TURNS` to avoid hitting the context limit. Older turns are dropped.

**Key insight:** Memory is not magic — it is just including past messages in the current request.

---

## 10. Key Concept: RAG

### What is RAG?

**RAG (Retrieval-Augmented Generation)** is a technique that lets an LLM answer questions about
documents without putting all those documents in the prompt every time.

Instead, documents are pre-processed into small chunks and each chunk is converted into a
**vector** (a list of ~1500 numbers that captures its meaning). These vectors are stored in a
**vector database** (ChromaDB). At query time, the question is converted to a vector and the
most semantically similar chunks are retrieved and given to the LLM.

### Why RAG instead of just sending all documents to the LLM?

| Approach | Problem |
|---|---|
| Send all documents in every prompt | Expensive (thousands of tokens), slow, hits context limits |
| Exact keyword search | Misses synonyms — "employment" won't find "work experience" |
| RAG (semantic vector search) | Finds relevant content by *meaning*, not exact words. Fast and cheap. |

### The RAG pipeline in this project

```
INGESTION (run once — data/ingest_kb.py):

  Markdown files → split into chunks → embed each chunk → store in ChromaDB
       ↓                   ↓                   ↓
  8 documents          43 chunks         43 vectors
  (career, expertise,  (~600 chars each) (text-embedding-3-small)
   education)

QUERY TIME (KnowledgeBaseAgent, every request):

  User question
       ↓
  Embed question (same model: text-embedding-3-small)
       ↓
  ChromaDB: cosine similarity search → top 5 most similar chunks
       ↓
  Claude haiku reads the 5 chunks + answers the question
       ↓
  Answer returned to Orchestrator
```

### What is a vector? (plain English)

Imagine plotting every word in a 3D space. "King" and "Queen" are close together. "King" and
"Banana" are far apart. Embedding models do this in 1,500+ dimensions, not 3 — so they can
capture subtle semantic relationships that simple word matching cannot.

When you embed "design philosophy" and embed a chunk about "UX approach and methodology",
they land near each other in that high-dimensional space — so the search finds it.

### Cosine similarity

The search uses **cosine similarity** — it measures the angle between two vectors. An angle
of 0° means identical meaning (similarity = 1.0). An angle of 90° means completely unrelated
(similarity = 0.0). ChromaDB finds the chunks with the smallest angle to the query vector.

### RAG vs the other agents in this project

| | RAG (KnowledgeBaseAgent) | Direct fetch (other agents) |
|---|---|---|
| Data freshness | Pre-indexed (stale if docs change) | Always live |
| Best for | Large narrative documents | Structured data, live data |
| Retrieval | Semantic similarity | SQL / API / web scrape |
| Setup | Run ingest once | No setup |
| Scales to | Thousands of documents | Small datasets |

---

## 11. Key Concept: Multi-Provider Support

The orchestrator supports three LLM providers. Switch with one line in `config.py`:

```python
LLM_PROVIDER = "anthropic"   # Claude sonnet-4-6 (best quality)
LLM_PROVIDER = "openai"      # GPT-4o-mini (fast, widely available)
LLM_PROVIDER = "ollama"      # Llama3.2 locally (free, private, no API key needed)
```

### Why do Anthropic and OpenAI have different code paths?

The two SDKs have different response formats:

```python
# Anthropic:
response.stop_reason          # "end_turn" or "tool_use"
response.content              # list of content blocks
block.input                   # already a Python dict

# OpenAI / Ollama:
choice.finish_reason          # "stop" or "tool_calls"
choice.message.tool_calls     # list of tool call objects
tc.function.arguments         # JSON string → needs json.loads()
```

Tool results are also sent differently:

```python
# Anthropic — all results in one "user" message:
{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]}

# OpenAI — one "tool" message per result:
{"role": "tool", "tool_call_id": "...", "content": "..."}
```

The orchestrator has two private methods — `_run_anthropic()` and `_run_openai()` — that
handle each format, sharing the same `_run_tools_parallel()` for the actual agent execution.

### Ollama notes

Ollama runs models locally on your machine. No API key, no cost, fully private. Trade-off:
smaller models are less reliable at tool calling. `llama3.2` works but `qwen2.5:7b` or
`llama3.1:8b` are better choices for tool-heavy queries.

---

## 12. Key Files — Annotated Walkthroughs

### `config.py` — All settings in one place

```python
LLM_PROVIDER = "anthropic"         # Switch to "openai" or "ollama" here

ORCHESTRATOR_MODEL = (             # Auto-selected based on LLM_PROVIDER
    "claude-sonnet-4-6" if LLM_PROVIDER == "anthropic"
    else "gpt-4o-mini"  if LLM_PROVIDER == "openai"
    else OLLAMA_MODEL
)
```

This is the **single source of truth** for every setting. Nothing is hardcoded elsewhere.

---

### `tools/definitions.py` — The menu Claude reads

Each tool definition tells Claude three things:
1. What the tool is **called** (`name`)
2. **When** to use it (`description`) ← most important
3. What **arguments** to pass (`input_schema`)

The file defines tools in Anthropic format and auto-generates the OpenAI format via list
comprehension — so you only maintain one set of definitions.

---

### `agents/base_agent.py` — The contract all agents follow

```python
class BaseAgent(ABC):
    @abstractmethod
    def run(self, question: str) -> str:
        ...
```

Every agent takes a question string and returns a string. The orchestrator doesn't care how
they work internally — just that they honour this contract.

---

### `agents/sqlite_agent.py` — NL → SQL → result

```
Question (NL)
     │
     ▼  Claude haiku: "Write SQL for this question given this schema"
SQL query
     │
     ▼  sqlite3: execute query against personal.db
     │
     ▼  JSON rows → returned to orchestrator
```

This is called **NL→SQL** (Natural Language to SQL). The LLM translates between human
language and database query language. The schema is injected into the prompt so Claude knows
what tables and columns exist.

---

### `agents/portfolio_agent.py` — Live web scraping

```
HTTP GET to sobhandutta.myportfolio.com/about
     │
     ▼  BeautifulSoup: strip scripts/styles, extract plain text
     │
     ▼  Claude haiku: answer question from the page content
     │
     ▼  Return answer
```

The page is fetched fresh on every call. A fake browser User-Agent header avoids being blocked.

---

### `agents/gmail_agent.py` — Two chained LLM calls

```
Question (NL)
     │
     ▼  LLM Call 1 (haiku): "Convert to Gmail search query"
     │  e.g. "subject:interview newer_than:7d"
     ▼
Gmail API: search inbox, fetch full email content (Base64 decoded)
     │
     ▼  LLM Call 2 (haiku): "Answer the question from these emails"
     │
     ▼  Return answer
```

Two LLM calls per query. The first translates intent into Gmail's search syntax. The second
reads the fetched emails and answers the original question.

---

### `agents/knowledge_base_agent.py` — RAG in action

```
Question
     │
     ▼  OpenAI: embed question → vector (1500 floats)
     │
     ▼  ChromaDB: cosine similarity search → top 5 chunks
     │
     ▼  Build context: format chunks with source labels
     │
     ▼  Claude haiku: answer question from chunks only
     │
     ▼  Return answer with source citations
```

The only agent that uses **two different API clients**: OpenAI for embedding (must match
ingestion model) and Anthropic for answer generation.

**Why can't you use Anthropic for embeddings?** Anthropic does not currently provide an
embedding API. Embeddings and text generation are separate capabilities from different providers.

---

### `orchestrator.py` — The core of everything

Key things to notice:

1. **Provider routing** — `run()` delegates to `_run_anthropic()` or `_run_openai()` based
   on `LLM_PROVIDER`. Both paths share `_run_tools_parallel()`.

2. **`_run_tools_parallel()`** — takes `(id, name, input_dict)` tuples and fans them out
   across a `ThreadPoolExecutor`. The futures dict maps each Future back to its call_id
   so results are correctly matched even when they finish out of order.

3. **The `while True` loop** — runs until the LLM produces a final text response. Usually
   2 iterations: (1) LLM picks tools, (2) LLM reads results and writes answer.

4. **`messages` grows each iteration** — every loop appends the assistant's tool-use turn
   and the tool results. This growing list is what gives the LLM "memory" of what it already
   asked and what it learned within one request.

---

### `data/ingest_kb.py` — Building the RAG vector store

Run this **once** (or after updating knowledge_base/ files) to build the vector store:

```bash
python data/ingest_kb.py
```

Three steps:
1. **Load** — reads all `.md` files from `knowledge_base/`
2. **Chunk** — splits text into 600-char chunks with 100-char overlap
3. **Embed & store** — embeds all chunks with OpenAI, stores in ChromaDB at `vector_store/`

The `vector_store/` directory is gitignored — it's a generated binary file, not source code.

---

## 13. How to Run It

### Prerequisites

```bash
# You need API keys for:
# - Anthropic (required for default setup)
# - OpenAI (required for embeddings + if using LLM_PROVIDER="openai")
# Ollama requires no key — install from https://ollama.com

# Navigate to the project
cd sobhan-projects/agentic
```

### First time setup

```bash
# 1. Copy and fill in your API keys
cp .env.example .env
# Edit .env:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...   (needed for embeddings even with LLM_PROVIDER="anthropic")

# 2. Seed your personal database
#    (edit data/seed_db.py with your real info first)
python data/seed_db.py

# 3. Build the RAG vector store
python data/ingest_kb.py
#    → Loads 8 documents, creates 43 chunks, embeds and stores in vector_store/

# 4. Launch the app
python main.py
#    → Opens at http://127.0.0.1:7860
```

### Switching LLM provider

Edit one line in `config.py`:

```python
LLM_PROVIDER = "anthropic"   # default
LLM_PROVIDER = "openai"      # requires OPENAI_API_KEY in .env
LLM_PROVIDER = "ollama"      # requires Ollama running locally: `ollama run llama3.2`
```

### Updating your knowledge base

Edit any `.md` files in `knowledge_base/`, then rebuild the vector store:

```bash
python data/ingest_kb.py
```

### Updating your personal database

Edit the data lists in `data/seed_db.py`, then re-run:

```bash
python data/seed_db.py
```

---

## 14. Enable Google Drive + Gmail

These agents degrade gracefully — they return a helpful message if not authenticated.
Follow these steps when you're ready to connect real Google data:

### Step 1: Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Google Drive API**
4. Enable **Gmail API**

### Step 2: Create OAuth credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Download the JSON file
5. Rename it to `client_secret.json`
6. Place it at `auth/credentials/client_secret.json`

### Step 3: Authenticate

```bash
python auth/google_auth.py
```

A browser window opens → log in → grant permissions.
A `token.json` is saved automatically — future runs use it silently (auto-refreshed when expired).

### What the scopes mean

- `drive.readonly` — read Drive files, cannot modify them
- `gmail.readonly` — read emails, cannot send or delete

Both are read-only. Safe.

---

## 15. Demo Queries to Try

### Simple — one agent

| Query | Agent called |
|---|---|
| "What are my skills?" | SQLiteAgent |
| "What companies have I worked at?" | SQLiteAgent |
| "What is on my portfolio website?" | PortfolioAgent |
| "What is my design philosophy?" | KnowledgeBaseAgent |
| "How do I approach team building?" | KnowledgeBaseAgent |
| "Do I have any recent job offer emails?" | GmailAgent |
| "Summarize my CV from Google Drive" | DriveAgent |

### Multi-agent — parallel dispatch

| Query | Agents called |
|---|---|
| "Tell me about my work at Elisity in detail" | SQLiteAgent + KnowledgeBaseAgent |
| "What are my skills and what does my portfolio say about me?" | SQLiteAgent + PortfolioAgent |
| "Give me a full professional summary" | SQLiteAgent + PortfolioAgent + KnowledgeBaseAgent |
| "Any interview emails and what is my leadership style?" | GmailAgent + KnowledgeBaseAgent |

### Memory — follow-up questions

Ask any question, then follow up:
- "Tell me more about that"
- "What about my education?"
- "How does that compare to my earlier work?"

---

## 16. Cost Strategy

Each user query triggers multiple LLM calls. Here is how costs are managed:

```
User query:
  Orchestrator: sonnet-4-6          [reasoning + synthesis]    ← 1-2 calls
  SQLiteAgent:  haiku-4-5           [SQL generation]           ← 1 call
  PortfolioAgent: haiku-4-5         [page QA]                  ← 1 call
  DriveAgent:   haiku-4-5           [doc summarisation]        ← 1 call
  GmailAgent:   haiku-4-5           [query gen + email QA]     ← 2 calls
  KnowledgeBaseAgent: haiku-4-5     [chunk QA]                 ← 1 call
  + OpenAI embedding: text-embedding-3-small                   ← 1 call (tiny)
```

**Typical cost per query:** ~$0.003–0.008

**Cost controls in `config.py`:**
- `MAX_AGENT_OUTPUT_CHARS = 3000` — truncates agent output so it doesn't overflow context
- `MAX_MEMORY_TURNS = 10` — limits how much history is sent per call

**Cost controls in `knowledge_base_agent.py`:**
- `TOP_K = 5` — only the 5 most relevant chunks go to Claude (not all 43)
- `CHUNK_SIZE = 600` — small chunks keep each embedding call minimal

**Free option:** Set `LLM_PROVIDER = "ollama"` — all LLM calls are local and free.
You still need OpenAI for embeddings, but at ~$0.00002 per query that is essentially zero.

---

## 17. What to Study Next

### Immediate extensions to this project

- **Re-ranker** — after vector search, use an LLM to re-order chunks by relevance
  (the `rag-experiment/pro_implementation/` folder shows this pattern)
- **Query rewriting** — have the LLM rephrase vague questions before embedding them
  (handles follow-ups like "tell me more about her" that lack context)
- **Streaming** — use `client.messages.stream()` for real-time token output in Gradio
- **Prompt caching** — cache the system prompt with Anthropic's cache header to cut costs 90%
- **Permanent memory** — after each conversation, store key facts back into the SQLite DB

### Deeper agentic patterns

- **ReAct** — agents that reason step by step before acting (original paper: Yao et al. 2022)
- **Planning agents** — LLM writes a plan, then executes each step in sequence
- **Self-reflection** — agent checks its own output and retries if wrong
- **Agent-to-agent communication** — sub-agents that can invoke each other

### Frameworks to explore (after mastering the raw patterns here)

- **LangGraph** — graph-based agent orchestration, good for complex conditional flows
- **CrewAI** — role-based multi-agent teams
- **Autogen** — Microsoft's conversational multi-agent framework

The reason to build this project *without* a framework first: you can see every moving part.
When you pick up LangGraph later, you will understand exactly what it is doing underneath —
and you will know when it is getting in your way.

---

## Quick Reference

### Key constants (config.py)

| Constant | Default | What it controls |
|---|---|---|
| `LLM_PROVIDER` | `"anthropic"` | Which LLM provider to use |
| `ORCHESTRATOR_MODEL` | `claude-sonnet-4-6` | Auto-set from LLM_PROVIDER |
| `SUBAGENT_MODEL` | `claude-haiku-4-5-20251001` | Model for SQL/summarisation tasks |
| `MAX_MEMORY_TURNS` | `10` | Max conversation turns kept in context |
| `MAX_AGENT_OUTPUT_CHARS` | `3000` | Max characters returned by each agent |

### Useful debugging commands

```bash
# Inspect the SQLite database
python -c "
import sqlite3, json
conn = sqlite3.connect('data/personal.db')
for t in ['profile','skills','experience','projects','education']:
    print(t, '->', conn.execute(f'SELECT * FROM {t}').fetchall())
"

# Check how many chunks are in the vector store
python -c "
from chromadb import PersistentClient
c = PersistentClient(path='vector_store')
col = c.get_collection('sobhan_knowledge_base')
print(f'Vector store: {col.count()} chunks')
"

# Test a single agent in isolation
python -c "
from agents import SQLiteAgent
print(SQLiteAgent().run('What are my top skills?'))
"

# Test the RAG agent in isolation
python -c "
from agents import KnowledgeBaseAgent
print(KnowledgeBaseAgent().run('What is Sobhan\'s design philosophy?'))
"

# Test the orchestrator without the UI
python -c "
from orchestrator import Orchestrator
print(Orchestrator().run('Give me a professional summary', []))
"
```

### Two-minute mental model of RAG

```
BEFORE (naïve): Send all documents to LLM every time
  → Expensive, slow, hits token limits

AFTER (RAG):
  Ingest once:   documents → chunks → vectors (stored in ChromaDB)
  Query time:    question → vector → find similar chunks → LLM answers from chunks
  → Fast, cheap, scales to thousands of documents
```
