"""
data/ingest_kb.py — Build the RAG vector store from the knowledge base.

Run this ONCE before starting the app to build the vector store:
    python data/ingest_kb.py

What it does:
    1. Reads all .md files from knowledge_base/ (career, expertise, education)
    2. Splits each document into overlapping text chunks
    3. Embeds each chunk using OpenAI text-embedding-3-small
    4. Stores all vectors in ChromaDB at vector_store/

RAG concept:
    Instead of sending entire documents to the LLM (expensive, slow),
    we pre-process documents into small chunks and convert each chunk
    into a vector (a list of numbers that captures its meaning).
    At query time, we convert the question to a vector and find the
    most similar chunks — only those relevant chunks go to the LLM.

    Documents → chunks → vectors → stored in ChromaDB
    (this script)              ↑
                          query time: question → vector → search
"""

import os
import sys
from pathlib import Path

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from chromadb import PersistentClient
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

# Path to the markdown knowledge base documents
KB_PATH = Path(__file__).parent.parent / "knowledge_base"

# Path where ChromaDB will persist the vector store on disk
VECTOR_STORE_PATH = str(Path(__file__).parent.parent / "vector_store")

# Collection name inside ChromaDB (must match KnowledgeBaseAgent)
COLLECTION_NAME = "sobhan_knowledge_base"

# OpenAI embedding model — text-embedding-3-small is fast, cheap, and high quality.
# IMPORTANT: this must match the model used in KnowledgeBaseAgent at query time.
# Mixing models produces garbage results (vectors live in different spaces).
EMBEDDING_MODEL = "text-embedding-3-small"

# Chunk size in characters. Smaller = more precise retrieval but less context per chunk.
# 600 chars is roughly 100-120 words — enough for a coherent paragraph.
CHUNK_SIZE = 600

# Overlap between consecutive chunks in characters.
# Overlap ensures sentences that span chunk boundaries appear in both chunks,
# preventing important information from being split and lost.
CHUNK_OVERLAP = 100

# ── Step 1: Load documents ────────────────────────────────────────────────────

def load_documents() -> list[dict]:
    """
    Walk the knowledge_base/ directory and read every .md file.
    Returns a list of dicts: { path, category, text }
    """
    documents = []

    for md_file in sorted(KB_PATH.rglob("*.md")):
        # The parent folder name is the category (career, expertise, education)
        category = md_file.parent.name
        text = md_file.read_text(encoding="utf-8")
        documents.append({
            "path": str(md_file),
            "category": category,
            "filename": md_file.stem,   # filename without extension e.g. "ataya"
            "text": text,
        })

    print(f"Loaded {len(documents)} documents from {KB_PATH}")
    return documents

# ── Step 2: Split into chunks ─────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks of fixed character size.

    Example with chunk_size=10, overlap=3:
        text = "abcdefghijklmnopqrst"
        chunks = ["abcdefghij", "hijklmnopq", "opqrstuvwx"]
                          ^^^               ^^^
                        (3-char overlap)  (3-char overlap)

    Why overlap?
        A sentence might start near the end of one chunk and finish at the
        start of the next. Without overlap, it gets split and neither chunk
        has the complete thought. Overlap ensures boundary content appears
        in at least one complete chunk.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        # Move forward by (chunk_size - overlap) so the next chunk
        # starts overlap characters before the end of this one.
        start += chunk_size - overlap

    return chunks


def create_chunks(documents: list[dict]) -> list[dict]:
    """
    Split all documents into chunks and attach metadata.
    Returns a flat list of chunk dicts: { text, source, category, chunk_index }
    """
    all_chunks = []

    for doc in documents:
        text_chunks = chunk_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)

        for i, chunk_text_str in enumerate(text_chunks):
            # Skip very short chunks (e.g. trailing whitespace at end of file)
            if len(chunk_text_str.strip()) < 50:
                continue

            all_chunks.append({
                "text": chunk_text_str,
                "source": doc["filename"],       # e.g. "ataya"
                "category": doc["category"],     # e.g. "career"
                "chunk_index": i,
            })

    print(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
    return all_chunks

# ── Step 3: Embed and persist ─────────────────────────────────────────────────

def embed_and_store(chunks: list[dict]):
    """
    Embed all chunks with OpenAI and store them in ChromaDB.

    Why batch embedding?
        Sending all texts in one API call is far more efficient than
        making one HTTP request per chunk. The OpenAI API accepts up
        to 2048 inputs per call.

    Why ChromaDB?
        ChromaDB is a vector database that stores both the embedding vectors
        and the original text. At query time, it uses HNSW (Hierarchical
        Navigable Small World) approximate nearest-neighbour search to find
        the most similar vectors to the query embedding in milliseconds.
    """
    client = OpenAI()
    chroma = PersistentClient(path=VECTOR_STORE_PATH)

    # Delete the collection if it exists to ensure a fresh, clean rebuild
    existing = [c.name for c in chroma.list_collections()]
    if COLLECTION_NAME in existing:
        chroma.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'")

    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        # cosine distance is standard for text embeddings — measures the
        # angle between vectors (semantic similarity) not their magnitude
        metadata={"hnsw:space": "cosine"},
    )

    texts = [chunk["text"] for chunk in chunks]

    print(f"Embedding {len(texts)} chunks with {EMBEDDING_MODEL}...")

    # Batch embed all chunks in one API call
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    vectors = [item.embedding for item in response.data]

    # Build metadata list — stored alongside each vector in ChromaDB
    # so we can show the source document in the agent's answer
    metadatas = [
        {
            "source": chunk["source"],
            "category": chunk["category"],
            "chunk_index": chunk["chunk_index"],
        }
        for chunk in chunks
    ]

    # String IDs required by ChromaDB
    ids = [f"{chunk['source']}_{chunk['chunk_index']}" for chunk in chunks]

    # Add everything to ChromaDB in one call
    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=texts,        # the raw text — returned at query time
        metadatas=metadatas,    # source metadata — returned at query time
    )

    print(f"Vector store built: {collection.count()} chunks stored at {VECTOR_STORE_PATH}/")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Building RAG Vector Store ===\n")
    documents = load_documents()
    chunks = create_chunks(documents)
    embed_and_store(chunks)
    print("\n=== Done! Vector store is ready. ===")
    print("You can now start the app and ask questions using query_knowledge_base.")
