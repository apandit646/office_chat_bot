"""Central configuration, read from environment variables / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Folder that holds the policy PDFs to index
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
# Where ChromaDB persists the embeddings
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", BASE_DIR / "chroma_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "office_policies")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("TOP_K", "4"))


def require_api_key() -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return GOOGLE_API_KEY
