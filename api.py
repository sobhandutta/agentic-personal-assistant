"""
api.py — FastAPI app: WebSocket streaming chat + static file serving.

Runs alongside the existing Gradio app (app.py / main.py) — they are
independent processes sharing the same Orchestrator code.

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Then open http://localhost:8000 for the custom UI.
Gradio remains available separately via: python main.py (port 7860)
"""

import logging
import traceback
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(format=_LOG_FORMAT, level=logging.INFO)
log = logging.getLogger("api")

# ── Build vector store on startup (same as app.py / main.py) ─────────────────
sys.path.insert(0, str(Path(__file__).parent))

def _build_vector_store():
    log.info("Building RAG vector store from knowledge_base/...")
    try:
        from data.ingest_kb import load_documents, create_chunks, embed_and_store
        documents = load_documents()
        if not documents:
            log.warning("No markdown files found in knowledge_base/ — skipping.")
            return
        chunks = create_chunks(documents)
        embed_and_store(chunks)
        log.info("Vector store ready.")
    except Exception:
        log.error("Failed to build vector store:\n%s", traceback.format_exc())
        log.warning("KnowledgeBaseAgent will be unavailable.")

_build_vector_store()

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from orchestrator import Orchestrator

app = FastAPI(title="Personal Assistant API")

# Single shared Orchestrator instance — run_stream() uses only local state
# per invocation, so concurrent WebSocket connections are safe.
_orc = Orchestrator()

STATIC_DIR = Path(__file__).parent / "static"

# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    log.info("WebSocket client connected: %s", websocket.client)
    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()
            history = data.get("history", [])

            if not user_message:
                await websocket.send_json({"type": "error", "text": "Empty message."})
                continue

            log.info("WS message: %s", user_message[:120])
            async for chunk in _orc.run_stream(user_message, history):
                await websocket.send_json(chunk)

    except WebSocketDisconnect:
        log.info("WebSocket client disconnected: %s", websocket.client)
    except Exception:
        log.exception("Unexpected error in ws_chat()")
        try:
            await websocket.send_json({"type": "error", "text": "Server error."})
        except Exception:
            pass

# ── Static file serving ───────────────────────────────────────────────────────
# Root returns index.html directly; /static/ serves CSS and JS.
# Routes are registered before StaticFiles mount so /ws/chat is matched first.

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
