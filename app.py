import streamlit as st

import db
import ingest
import search

st.set_page_config(page_title="Staff Report Retrieval", layout="wide")


def render_pdf_link(storage_path: str, page_number: int, label: str):
    try:
        url = db.get_pdf_public_url(storage_path)
    except Exception as e:
        st.caption(f"⚠️ Could not build source link: {e}")
        return
    # Most PDF viewers (including browser-native ones) respect #page=N.
    st.markdown(f"[📄 Open source PDF at page {page_number or 1}]({url}#page={page_number or 1})")


tab_search, tab_admin = st.tabs(["🔍 Search", "🛠 Admin / Ingest"])

with tab_search:
    st.title("Historical Staff Report Search")
    st.caption(
        "Returns exact, verbatim paragraphs from historical staff reports. "
        "Nothing here is generated — every result is source-linked."
    )

    try:
        n_reports, n_chunks = db.report_count(), db.chunk_count()
        st.caption(f"Corpus: {n_reports} reports · {n_chunks} indexed paragraphs")
    except Exception as e:
        st.error(f"Can't reach the database: {e}")
        st.stop()

    col_q, col_k = st.columns([4, 1])
    query_text = col_q.text_input(
        "Query",
        placeholder='e.g. "language used for community character in residential additions"',
        label_visibility="collapsed",
    )
    top_k = col_k.slider("Results", min_value=3, max_value=25, value=8, label_visibility="collapsed")
    permit_filter = st.text_input("Filter by exact permit number (optional)", value="")

    if query_text:
        if n_chunks == 0:
            st.warning("No documents ingested yet — use the Admin tab to run a batch upload first.")
        else:
            with st.spinner("Searching..."):
                results = search.search(query_text, top_k=top_k, permit_filter=permit_filter or None)
            if not results:
                st.info("No matching paragraphs found.")
            for r in results:
                with st.container(border=True):
                    badge_cols = st.columns([2, 3, 2])
                    badge_cols[0].markdown(f"**Permit:** {r['permit_number'] or '—'}")
                    badge_cols[1].markdown(f"**Address:** {r['project_address'] or '—'}")
                    badge_cols[2].markdown(
                        f"**Section:** {r['section_header'] or '—'} · p.{r['page_number'] or '?'}"
                    )
                    st.write(r["chunk_text"])
                    with st.expander("Source & report metadata"):
                        st.caption(f"Scope of work: {r['scope_summary'] or 'not extracted'}")
                        render_pdf_link(r["storage_path"], r["page_number"], r["original_filename"])

with tab_admin:
    st.title("Batch Ingestion")
    st.caption(
        "Upload this month's staff report PDFs, then run ingestion. Each PDF "
        "is parsed, chunked, embedded, and sent to an LLM once for metadata "
        "extraction (permit #, address, scope)."
    )

    uploaded_files = st.file_uploader(
        "Drop PDF staff reports here", type=["pdf"], accept_multiple_files=True
    )

    if uploaded_files and st.button("Run ingestion now", type="primary"):
        payload = [(f.name, f.getvalue()) for f in uploaded_files]
        with st.spinner(f"Ingesting {len(payload)} file(s)... this calls the LLM once per document."):
            results = ingest.run_ingestion(payload)
        st.write(results)
        ok = sum(1 for r in results if r["status"] == "ingested")
        st.success(f"Ingested {ok}/{len(results)} file(s).")

    st.divider()
    st.subheader("Recently ingested reports")
    try:
        rows = db.list_reports(limit=50)
    except Exception as e:
        rows = []
        st.error(f"Can't reach the database: {e}")

    if rows:
        st.dataframe(
            [
                {
                    "Permit #": r["permit_number"],
                    "Address": r["project_address"],
                    "Scope": (r["scope_summary"] or "")[:120],
                    "File": r["original_filename"],
                    "Ingested": r["ingested_at"],
                }
                for r in rows
            ],
            use_container_width=True,
        )
    else:
        st.caption("Nothing ingested yet.")
