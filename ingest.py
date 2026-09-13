"""
Phase 1 entry point — Website Edition. Called directly from the
Streamlit Admin tab with the bytes of an uploaded file. There is no
local inbox/ folder here: uploaded files go straight from browser
memory to Supabase Storage, since Streamlit Cloud's local disk doesn't
persist between restarts.
"""
import db
import embeddings
import extraction


def ingest_uploaded_pdf(filename: str, pdf_bytes: bytes) -> dict:
    if db.report_already_ingested(filename):
        return {"file": filename, "status": "skipped (already ingested)"}

    pages = extraction.extract_pages(pdf_bytes)
    if not any(p.strip() for p in pages):
        return {
            "file": filename,
            "status": "skipped (no extractable text — likely a scanned image PDF, needs OCR)",
        }

    metadata = extraction.extract_metadata_via_llm(pages)
    chunks = extraction.chunk_pages(pages)

    storage_path = filename  # relies on report_already_ingested() to prevent collisions
    db.upload_pdf(storage_path, pdf_bytes)

    report_id = db.insert_report(
        permit_number=metadata["permit_number"],
        project_address=metadata["project_address"],
        scope_summary=metadata["scope_summary"],
        original_filename=filename,
        storage_path=storage_path,
        page_count=len(pages),
    )

    if chunks:
        chunk_embeddings = embeddings.embed_documents([c["chunk_text"] for c in chunks])
        db.insert_chunks(report_id, chunks, chunk_embeddings)

    return {
        "file": filename,
        "status": "ingested",
        "permit_number": metadata["permit_number"],
        "project_address": metadata["project_address"],
        "chunks": len(chunks),
    }


def run_ingestion(uploaded_files: list[tuple[str, bytes]]) -> list[dict]:
    """uploaded_files: list of (filename, bytes) tuples, e.g. from
    Streamlit's file_uploader."""
    return [ingest_uploaded_pdf(name, data) for name, data in uploaded_files]
