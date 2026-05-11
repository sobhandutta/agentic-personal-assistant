"""
KnowledgeBaseAgent — demonstrates the RAG (Retrieval-Augmented Generation) pattern.

How RAG works (vs the other agents in this project):

  Other agents (SQLite, Portfolio, Drive, Gmail):
    → Fetch LIVE data on demand every time a question is asked
    → Good for: real-time data (emails, live website, current DB records)

  KnowledgeBaseAgent (RAG):
    → Data is PRE-INDEXED into a vector store (run ingest_kb.py once)
    → At query time: embed question → find similar chunks → LLM answers
    → Good for: large document collections where semantic search beats exact lookup

RAG pipeline (this agent):
    Question
      ↓ embed (OpenAI text-embedding-3-small)
      ↓ search ChromaDB (cosine similarity → top K chunks)
      ↓ inject chunks into prompt
      ↓ LLM (Claude haiku) generates answer from chunks
      ↓ Return answer to Orchestrator
"""

import anthropic
from openai import OpenAI
from chromadb import PersistentClient
from pathlib import Path

from .base_agent import BaseAgent
from config import SUBAGENT_MODEL

# ── Configuration — must match data/ingest_kb.py ─────────────────────────────

# Path to the ChromaDB vector store built by data/ingest_kb.py
VECTOR_STORE_PATH = str(Path(__file__).parent.parent / "vector_store")

# Must match EXACTLY the model used in ingest_kb.py.
# Queries and documents must live in the same vector space (same model).
EMBEDDING_MODEL = "text-embedding-3-small"

# Collection name inside ChromaDB — must match ingest_kb.py
COLLECTION_NAME = "sobhan_knowledge_base"

# How many chunks to retrieve from the vector store.
# More chunks = more context for the LLM, but also more tokens and cost.
TOP_K = 5

# System prompt for the answer generation step.
_SYSTEM_PROMPT = """You are a knowledgeable assistant about Sobhan Dutta's career, expertise,
and background. Answer the question based solely on the provided document excerpts from the
knowledge base. Be concise and cite which document the information came from when relevant.
If the answer is not in the provided context, say so clearly."""


class KnowledgeBaseAgent(BaseAgent):
    """
    RAG agent that retrieves relevant document chunks from ChromaDB
    and uses Claude to generate an answer grounded in those chunks.
    """

    def __init__(self):
        # Anthropic client — used for the final answer generation step
        self.anthropic = anthropic.Anthropic()

        # OpenAI client — used ONLY for embedding the query.
        # We use OpenAI embeddings because the vector store was built with them.
        self.openai = OpenAI()

        # Connect to the ChromaDB vector store on disk.
        # PersistentClient reads the existing database built by ingest_kb.py.
        # _service_available tracks whether the vector store exists and is loaded.
        self._collection = None
        self._load_collection()

    def _load_collection(self):
        """
        Try to connect to the ChromaDB collection.
        Sets self._collection to None if the vector store hasn't been built yet.
        """
        try:
            chroma = PersistentClient(path=VECTOR_STORE_PATH)
            self._collection = chroma.get_collection(COLLECTION_NAME)
        except Exception:
            # Vector store doesn't exist yet — user needs to run ingest_kb.py
            self._collection = None

    def _embed_query(self, question: str) -> list[float]:
        """
        Convert the question text into a vector using the same embedding model
        that was used to build the vector store.

        Why embed the query?
            ChromaDB stores document chunks as vectors (lists of ~1500 floats).
            To find similar chunks, we must express the query in the same
            vector space. The embedding model maps both queries and documents
            to points in that space — similar meaning = nearby points.
        """
        response = self.openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[question],
        )
        # response.data is a list; [0].embedding is the vector for our single input
        return response.data[0].embedding

    def _retrieve_chunks(self, question: str) -> list[dict]:
        """
        Embed the question and search ChromaDB for the TOP_K most similar chunks.

        Returns a list of dicts: { text, source, category }

        How ChromaDB search works:
            1. The query vector is compared against all stored vectors using
               cosine similarity (measures the angle between vectors).
            2. Chunks with smaller cosine distance are more semantically similar.
            3. ChromaDB uses HNSW (approximate nearest-neighbour) to do this
               in milliseconds even across thousands of vectors.
        """
        query_vector = self._embed_query(question)

        # query() returns results sorted by similarity (closest first)
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

        # results contains parallel lists: documents[0], metadatas[0], distances[0]
        # We zip them together into a flat list of dicts for easy access
        chunks = []
        for text, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": text,
                "source": meta.get("source", "unknown"),
                "category": meta.get("category", "unknown"),
                "similarity": round(1 - distance, 3),  # convert distance → similarity score
            })

        return chunks

    def _build_context(self, chunks: list[dict]) -> str:
        """
        Format the retrieved chunks into a readable context block for the LLM.

        We label each chunk with its source document so the LLM can cite it.
        The similarity score helps the LLM judge how relevant each chunk is.
        """
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[Chunk {i} | Source: {chunk['source']} | "
                f"Category: {chunk['category']} | "
                f"Similarity: {chunk['similarity']}]\n"
                f"{chunk['text']}"
            )
        return "\n\n---\n\n".join(parts)

    def run(self, question: str) -> str:
        """
        Full RAG pipeline: embed → retrieve → generate.

        This is the main entry point called by the Orchestrator.
        """
        # Guard: vector store must exist (built by running ingest_kb.py)
        if self._collection is None:
            return (
                "[KnowledgeBaseAgent] Vector store not found. "
                "Run `python data/ingest_kb.py` first to build it."
            )

        try:
            # ── Step 1: Retrieve relevant chunks ─────────────────────────────
            # Embed the question and find the TOP_K most similar chunks
            # from the pre-indexed knowledge base.
            chunks = self._retrieve_chunks(question)

            if not chunks:
                return "[KnowledgeBaseAgent] No relevant content found in the knowledge base."

            # ── Step 2: Build context from retrieved chunks ───────────────────
            # Format the chunks into a structured context block that the LLM
            # can read and reason over.
            context = self._build_context(chunks)

            # ── Step 3: Generate answer with Claude ───────────────────────────
            # Claude reads the retrieved chunks and generates a grounded answer.
            # It is instructed to only use the provided context — not its own
            # training knowledge — so the answer is accurate to the source docs.
            response = self.anthropic.messages.create(
                model=SUBAGENT_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Here are the most relevant excerpts from Sobhan's knowledge base:\n\n"
                        f"{context}\n\n"
                        f"Question: {question}"
                    ),
                }],
            )

            return response.content[0].text

        except Exception as e:
            return f"[KnowledgeBaseAgent error] {e}"
