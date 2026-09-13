"""
Central configuration — Website Edition.

Everything is read from environment variables. Locally that means a
.env file or exported shell vars; on Streamlit Community Cloud that
means the app's "Secrets" panel (Settings -> Secrets), which sets these
as environment variables automatically. Nothing here should ever be
hardcoded or committed to the repo.
"""
import os

# --- Supabase (database + vector search + PDF file storage, one account) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # use the "service_role" key, not "anon"
STORAGE_BUCKET = "staff-reports"

# --- LLM extraction (metadata only, never generates displayed text) ---
# LLM_PROVIDER=anthropic  -> uses ANTHROPIC_API_KEY
# LLM_PROVIDER=openrouter -> uses OPENROUTER_API_KEY (OpenAI-compatible)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
EXTRACTION_MODEL = os.environ.get(
    "EXTRACTION_MODEL",
    "claude-haiku-4-5-20251001" if LLM_PROVIDER == "anthropic" else "openai/gpt-5.6-luna",
)

# --- Embeddings (Voyage AI — lightweight API call, no local ML model,
# which matters on Streamlit Cloud's free tier resource limits) ---
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-3.5-lite")
EMBEDDING_DIM = 1024  # must match the vector(N) column in supabase_setup.sql

# How many pages of a report to feed the LLM for metadata extraction.
EXTRACTION_MAX_PAGES = 3

# Chunking
MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 1800
