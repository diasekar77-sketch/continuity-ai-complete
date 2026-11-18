import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional
    pass

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "continuity.db"))
CHROMA_PATH = os.getenv("CHROMA_PATH", str(ROOT / "data" / "chroma_store"))

# Any OpenAI-compatible provider (Groq, Gemini, Ollama, Zhipu/GLM, OpenAI ...).
# Old OPENAI_* names still work.
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

EMBEDDER = os.getenv("EMBEDDER", "auto")  # auto | sentence-transformers | hash
POLICY_MIN_SCORE = os.getenv("POLICY_MIN_SCORE")  # optional override
