"""
Supabase is the system of record for everything: report metadata,
chunk text + embeddings (in Postgres), and the PDF files themselves
(in Supabase Storage). This replaces the local-SQLite-plus-local-disk
setup from the desktop version, because Streamlit Community Cloud's
filesystem is wiped on every restart/redeploy — nothing written to
local disk there survives.
"""
from supabase import create_client, Client

import config

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY not set. Add them in Streamlit "
                "Secrets (or your local .env) before running ingestion or search."
            )
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


# --- Reports ---

def report_already_ingested(original_filename: str) -> bool:
    res = (get_client().table("reports")
           .select("id").eq("original_filename", original_filename).execute())
    return len(res.data) > 0


def insert_report(permit_number, project_address, scope_summary,
                   original_filename, storage_path, page_count) -> int:
    res = get_client().table("reports").insert({
        "permit_number": permit_number,
        "project_address": project_address,
        "scope_summary": scope_summary,
        "original_filename": original_filename,
        "storage_path": storage_path,
        "page_count": page_count,
    }).execute()
    return res.data[0]["id"]


def get_reports_by_ids(report_ids: list[int]) -> dict:
    if not report_ids:
        return {}
    res = get_client().table("reports").select("*").in_("id", report_ids).execute()
    return {r["id"]: r for r in res.data}


def list_reports(limit: int = 50) -> list[dict]:
    res = (get_client().table("reports").select("*")
           .order("ingested_at", desc=True).limit(limit).execute())
    return res.data


def report_count() -> int:
    res = get_client().table("reports").select("id", count="exact").execute()
    return res.count or 0


def chunk_count() -> int:
    res = get_client().table("chunks").select("id", count="exact").execute()
    return res.count or 0


# --- Chunks ---

def insert_chunks(report_id: int, chunks: list[dict], embeddings: list[list[float]]):
    """chunks: list of {chunk_index, section_header, page_number, chunk_text}"""
    rows = [
        {
            "report_id": report_id,
            "chunk_index": c["chunk_index"],
            "section_header": c["section_header"],
            "page_number": c["page_number"],
            "chunk_text": c["chunk_text"],
            "embedding": emb,
        }
        for c, emb in zip(chunks, embeddings)
    ]
    if rows:
        get_client().table("chunks").insert(rows).execute()


def get_chunks_by_ids(chunk_ids: list[int]) -> dict:
    if not chunk_ids:
        return {}
    res = get_client().table("chunks").select("*").in_("id", chunk_ids).execute()
    return {r["id"]: r for r in res.data}


# --- PDF file storage ---

def upload_pdf(storage_path: str, pdf_bytes: bytes):
    get_client().storage.from_(config.STORAGE_BUCKET).upload(
        storage_path, pdf_bytes, {"content-type": "application/pdf"}
    )


def get_pdf_public_url(storage_path: str) -> str:
    return get_client().storage.from_(config.STORAGE_BUCKET).get_public_url(storage_path)


def download_pdf(storage_path: str) -> bytes:
    return get_client().storage.from_(config.STORAGE_BUCKET).download(storage_path)
