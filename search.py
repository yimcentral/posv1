"""
Phase 2 core logic. The vector search itself runs inside Postgres
(the match_chunks SQL function in supabase_setup.sql) — this module
just embeds the query, calls it, and re-attaches report metadata.
As with the desktop version: what gets displayed is always the real
row from the reports/chunks tables, never a generative answer.
"""
import db
import embeddings


def search(query_text: str, top_k: int = 8, permit_filter: str = None):
    query_embedding = embeddings.embed_query(query_text)

    res = db.get_client().rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_count": top_k,
        "filter_permit": permit_filter,
    }).execute()
    hits = res.data or []
    if not hits:
        return []

    report_ids = list({h["report_id"] for h in hits})
    reports = db.get_reports_by_ids(report_ids)

    results = []
    for h in hits:
        report = reports.get(h["report_id"])
        if report is None:
            continue
        results.append({
            "chunk_text": h["chunk_text"],
            "section_header": h["section_header"],
            "page_number": h["page_number"],
            "similarity": h["similarity"],  # higher = more similar (0-1ish, cosine)
            "permit_number": report["permit_number"],
            "project_address": report["project_address"],
            "scope_summary": report["scope_summary"],
            "storage_path": report["storage_path"],
            "original_filename": report["original_filename"],
            "report_id": report["id"],
        })
    return results
