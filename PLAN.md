# Project Plan — Personal AI Assistant (Agentic)

A learning project that builds a personal AI assistant using real AI/ML engineering
patterns. Each item is a concrete concept you can study, not just a feature checkbox.

---

## Status Key

- ✅ Done
- 🔧 In progress / needs a small fix
- 📋 Planned — clear next step
- 💡 Idea — good learning concept, not yet scoped

---

## Part 1 — Foundation (Done)

### Architecture & Orchestration
- ✅ **Orchestrator** — central loop that receives a user message, decides which tools (agents) to call, and assembles the final answer (`orchestrator.py`)
- ✅ **Tool calling** — LLM returns structured tool calls (name + arguments); orchestrator dispatches them
- ✅ **Parallel tool dispatch** — multiple agents run concurrently via `ThreadPoolExecutor` so the user doesn't wait for them to run one-by-one
- ✅ **Base agent pattern** — shared `BaseAgent` class; all agents follow the same `run(input) → str` contract
- ✅ **Multi-provider LLM routing** — single `LLM_PROVIDER` switch in `config.py` selects Anthropic, OpenAI, or Ollama without changing any other file
- ✅ **Tool schema auto-conversion** — `TOOL_DEFINITIONS_OPENAI` is auto-generated from `TOOL_DEFINITIONS` so both providers see the right format

### Memory
- ✅ **Short-term conversation memory** — `ConversationMemory` converts Gradio history into Anthropic message format and trims to `MAX_MEMORY_TURNS`

### UI
- ✅ **Gradio chat interface** — `main.py` wires up the Gradio chatbot to the orchestrator

---

## Part 2 — Agents (Done)

| Agent | Tool name | Data source | Concept demonstrated |
|---|---|---|---|
| ✅ SQLiteAgent | `query_database` | `data/personal.db` | NL→SQL: LLM writes SQL from plain English |
| ✅ PortfolioAgent | `scrape_portfolio` | `sobhandutta.myportfolio.com` | Web scraping with BeautifulSoup |
| ✅ DriveAgent | `query_drive` | Google Drive folder | OAuth2 + Google API |
| ✅ GmailAgent | `search_gmail` | Gmail inbox | OAuth2 + Google API |
| ✅ KnowledgeBaseAgent | `query_knowledge_base` | ChromaDB vector store | RAG: embed → retrieve → generate |

---

## Part 3 — RAG Pipeline (Done)

- ✅ **Knowledge base documents** — 9 markdown files across 4 categories: `career/`, `expertise/`, `education/`, `youtube/`
- ✅ **Chunking** — sliding-window chunker in `data/ingest_kb.py` (chunk size 600, overlap 100)
- ✅ **OpenAI embeddings** — `text-embedding-3-small` (1,536 dimensions)
- ✅ **ChromaDB vector store** — local persistent store with HNSW index and cosine similarity
- ✅ **Semantic retrieval** — embed query → find top-5 similar chunks → inject into LLM prompt
- ✅ **RAG visualization notebook** — `rag_visualization.ipynb` with:
  - Document stats (chars, tokens, chunk counts)
  - Vector space stats and cosine similarity demo
  - 2D t-SNE cluster plot
  - 3D t-SNE cluster plot
  - Live query-with-highlight visualization

---

## Part 4 — Data (Done / Needs Fix)

- ✅ **`facts.jsonl`** — 73 facts about Sobhan across 6 categories (personal, work, achievements, skills, education, youtube) — stored in Google Drive
- ✅ **`youtube.jsonl`** — 23 YouTube video entries with category, title, description, type, duration, and URL — stored in Google Drive
- ✅ **`knowledge_base/`** — 9 markdown documents covering career, expertise, education, YouTube channel
- 🔧 **`data/seed_db.py`** — SQLite seed script has a bug: the YouTube project entry has 5 tuple elements but the `projects` table only has 4 columns. **Fix: run `python data/seed_db.py` after the correction in the file.**
- 🔧 **Vector store out of date** — `youtube/youtube.md` was added to `knowledge_base/` after the vector store was last built. The store has 43 chunks across 3 categories; `youtube` is missing. **Fix: run `python data/ingest_kb.py` to rebuild.**
- 📋 **Add remaining YouTube URLs** — 15 videos in `youtube.jsonl` still have `url: null`. Fill these in as the links become available.

---

## Part 5 — Documentation & Learning (Done)

- ✅ **`GUIDE.md`** — 17-section educational guide covering: agentic AI, architecture, mental model, file structure, tool calling loop, parallel dispatch, short-term memory, RAG concept, multi-provider support, key file walkthroughs, setup steps, demo queries, cost strategy
- ✅ **Inline comments** — every key file has educational line-by-line comments explaining the WHY behind each decision (orchestrator, agents, tools, memory, config)
- ✅ **Architecture ASCII diagram** — embedded in `orchestrator.py` module docstring
- ✅ **`PLAN.md`** — this file

---

## Part 6 — What's Next (Planned)

These are ordered from easiest to most complex. Each one teaches a new AI concept.

### Quick wins (1–2 hours each)

- 📋 **Fix `seed_db.py` and rebuild the DB** — Run `python data/seed_db.py` after the tuple-count fix, then verify with `sqlite3 data/personal.db ".tables"`
- 📋 **Rebuild vector store** — Run `python data/ingest_kb.py` to include the `youtube` category, then re-run `rag_visualization.ipynb` from the top
- 📋 **Metadata filtering in RAG** — Use ChromaDB's `where={"category": "career"}` filter to restrict retrieval to a specific category. Teaches: structured filtering on top of vector search
- 📋 **Token counting** — Replace `MAX_MEMORY_TURNS` (turn count) with actual token counting using `tiktoken`. Teaches: context window management, why token limits matter

### Medium tasks (half a day each)

- 📋 **Streaming responses** — Add `stream=True` to the Anthropic call and yield tokens to Gradio as they arrive. Teaches: streaming APIs, generator functions, UX improvement
- 📋 **Structured output (JSON mode)** — Force an agent to return a strict JSON schema (e.g., the SQLite agent returns `{columns: [...], rows: [...]}` instead of a string). Teaches: reliable LLM output parsing
- 📋 **Long-term persistent memory** — Save key facts extracted from conversations to a `memory.json` file; inject them as context in future sessions. Teaches: the difference between short-term (in-context) and long-term (external store) memory
- 📋 **Few-shot prompting** — Add 2–3 example Q&A pairs to the orchestrator system prompt to guide the LLM's style and reduce hallucination. Teaches: in-context learning

### Larger features (1–2 days each)

- 💡 **Hybrid search (BM25 + vector)** — Combine semantic search with keyword search for better RAG retrieval. Use `rank_bm25` library alongside ChromaDB. Teaches: why pure vector search fails on exact matches
- 💡 **Re-ranking** — After retrieving top-K chunks, pass them to a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM`) to re-score and reorder. Teaches: two-stage retrieval pipeline
- 💡 **Conversation summarization** — When history exceeds a token limit, summarize old turns into a single compressed paragraph and keep only recent turns verbatim. Teaches: episodic memory, recursive summarization
- 💡 **Self-reflection / chain-of-thought** — Add a reasoning step where the LLM thinks through the question before answering (`<thinking>...</thinking>` pattern or Claude's extended thinking). Teaches: CoT prompting, reasoning models
- 💡 **Evaluation (evals)** — Build a test script that runs 10 sample questions and scores answers automatically (exact match, keyword presence, or an LLM-as-judge). Teaches: how production teams measure model quality

### Advanced concepts (research-level)

- 💡 **Agent-to-agent communication** — Let one agent spawn and instruct another (sub-agent pattern). Teaches: hierarchical multi-agent systems
- 💡 **Planning agent (ReAct)** — A dedicated agent that breaks complex questions into sub-tasks, executes them in sequence, and synthesizes the result. Teaches: the Reasoning + Acting loop
- 💡 **Fine-tuning** — Fine-tune a small model (e.g., `gpt-4o-mini`) on Q&A pairs from your knowledge base. Teaches: when to use RAG vs. fine-tuning vs. both
- 💡 **Guardrails** — Validate LLM output before returning it (e.g., reject answers that contain information not present in the retrieved chunks). Teaches: output validation, hallucination detection
- 💡 **Observability / tracing** — Log every LLM call with latency, token count, cost, and which tools were called. Visualize in a dashboard. Teaches: production ML observability

---

## Immediate Action Items

| # | Task | Command |
|---|---|---|
| 1 | Fix SQLite seed bug | `python data/seed_db.py` |
| 2 | Rebuild vector store (add youtube category) | `python data/ingest_kb.py` |
| 3 | Re-run RAG visualization | Open `rag_visualization.ipynb` → Run All |
| 4 | Test the full assistant | `python main.py` |
