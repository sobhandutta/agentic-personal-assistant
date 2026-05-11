import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
GEMINI_BASE_URL    = "https://generativelanguage.googleapis.com/v1beta/openai/"
OLLAMA_BASE_URL    = "http://localhost:11434/v1"

# ── Model IDs (update if a model is retired) ──────────────────────────────
GPT_MODEL    = "gpt-4o-mini"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL = "gemini-1.5-flash"
OLLAMA_MODEL = "llama3.2"

LLM_PROVIDER = "anthropic"  # "anthropic" or "openai"

# ORCHESTRATOR_MODEL = "claude-sonnet-4-6" if LLM_PROVIDER == "anthropic" else OLLAMA_MODEL
ORCHESTRATOR_MODEL = (
    "claude-sonnet-4-6" if LLM_PROVIDER == "anthropic"
    else "gpt-4o-mini"  if LLM_PROVIDER == "openai"
    else OLLAMA_MODEL
)
SUBAGENT_MODEL = "claude-haiku-4-5-20251001"

# ── Create four clients — all using the same OpenAI SDK ───────────────────
# OpenAI-compatible wrapper. 
openai_client    = OpenAI()                                                               # GPT
anthropic_client = OpenAI(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)        # Claude
gemini_client    = OpenAI(api_key=GOOGLE_API_KEY,    base_url=GEMINI_BASE_URL)            # Gemini
ollama_client    = OpenAI(api_key="ollama",          base_url=OLLAMA_BASE_URL)            # Llama3

MAX_MEMORY_TURNS = 10
MAX_AGENT_OUTPUT_CHARS = 3000

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "personal.db")
PORTFOLIO_URL = "https://sobhandutta.myportfolio.com/about"
GOOGLE_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "auth", "credentials", "client_secret.json")
GOOGLE_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "auth", "credentials", "token.json")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# DriveAgent: only list files inside this folder (by exact name). Set GOOGLE_DRIVE_FOLDER_ID to skip lookup.
DRIVE_NOTES_FOLDER_NAME = os.getenv("GOOGLE_DRIVE_NOTES_FOLDER", "LLM Project Notes")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None
