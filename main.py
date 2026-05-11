"""
Entry point — Gradio chat UI.

Install
.venv/bin/pip install gradio
Run
.venv/bin/python3 main.py
Run:
    python main.py

Then open the local URL printed in the terminal.
"""

import logging
import traceback
import gradio as gr

# Set up logging BEFORE any app imports so our handlers are always registered,
# regardless of what Gradio/ChromaDB/httpx may have done to the root logger.
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_formatter = logging.Formatter(_LOG_FORMAT)
_file_handler = logging.FileHandler("app.log", mode="a")
_file_handler.setFormatter(_formatter)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_formatter)

def _get_logger(name: str) -> logging.Logger:
    """Return a logger with its own handlers, independent of root logger state."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(_file_handler)
        logger.addHandler(_stream_handler)
    logger.propagate = False  # don't double-log via root
    return logger

log = _get_logger("main")
_get_logger("orchestrator")  # pre-configure before import so orchestrator logs are captured

from orchestrator import Orchestrator  # noqa: E402 — must come after logging setup

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
    title="Ask About Me",
    description=(
        "Ask anything about Sobhan — work history, skills, projects, emails, or documents. "
        "Powered by Claude + 4 specialist sub-agents (SQLite · LinkedIn · Google Drive · Gmail)."
    ),
)

if __name__ == "__main__":
    demo.launch(show_error=True)
