"""
Entry point for Hugging Face Spaces — Gradio chat UI.

On startup:
  1. Builds the RAG vector store from knowledge_base/ markdown files.
  2. Launches the Gradio chat interface.

Local usage:
    python app.py
"""

import logging
import traceback
import sys
import os
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_formatter = logging.Formatter(_LOG_FORMAT)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_formatter)


def _get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(_stream_handler)
    logger.propagate = False
    return logger


log = _get_logger("main")
_get_logger("orchestrator")

# ── Startup: build vector store from knowledge_base/ markdown files ───────────

def _build_vector_store():
    """Build ChromaDB vector store from knowledge_base/ at startup."""
    log.info("Building RAG vector store from knowledge_base/...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from data.ingest_kb import load_documents, create_chunks, embed_and_store
        documents = load_documents()
        if not documents:
            log.warning("No markdown files found in knowledge_base/ — skipping vector store build.")
            return
        chunks = create_chunks(documents)
        embed_and_store(chunks)
        log.info("Vector store ready.")
    except Exception:
        log.error("Failed to build vector store:\n%s", traceback.format_exc())
        log.warning("KnowledgeBaseAgent will be unavailable.")


_build_vector_store()

# ── Launch Gradio ─────────────────────────────────────────────────────────────

import gradio as gr
from orchestrator import Orchestrator

orc = Orchestrator()


def chat(message: str, history: list) -> str:
    log.info("USER: %s", message)
    try:
        response = orc.run(message, history)
        log.info("RESPONSE: %s", response[:300])
        return response
    except Exception:
        log.error("Unhandled exception in chat():\n%s", traceback.format_exc())
        raise


demo = gr.ChatInterface(
    fn=chat,
    title="Ask About Sobhan",
    description=(
        "Ask anything about Sobhan — work history, skills, projects, or career. "
        "Powered by Claude + specialist sub-agents (SQLite · Portfolio · Knowledge Base)."
    ),
)

if __name__ == "__main__":
    demo.launch(show_error=True)
