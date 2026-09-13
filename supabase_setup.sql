-- Run this ONCE in Supabase: Dashboard -> SQL Editor -> New Query -> paste
-- this whole file -> Run. Safe to re-run (uses IF NOT EXISTS / OR REPLACE).

-- Enables vector similarity search.
create extension if not exists vector;

create table if not exists reports (
    id                  bigint generated always as identity primary key,
    permit_number       text,
    project_address     text,
    scope_summary       text,
    original_filename   text not null unique,
    storage_path        text not null,   -- path inside the "staff-reports" bucket
    page_count          int,
    ingested_at         timestamptz not null default now()
);

create table if not exists chunks (
    id                  bigint generated always as identity primary key,
    report_id           bigint not null references reports(id) on delete cascade,
    chunk_index         int not null,
    section_header      text,
    page_number         int,
    chunk_text          text not null,
    embedding           vector(1024)   -- must match config.EMBEDDING_DIM
);

create index if not exists idx_chunks_report_id on chunks(report_id);
create index if not exists idx_reports_permit on reports(permit_number);

-- Vector similarity search, called from the app via supabase.rpc(...).
-- Returns the top N most semantically similar chunks, optionally
-- restricted to one permit number.
create or replace function match_chunks(
    query_embedding vector(1024),
    match_count int default 8,
    filter_permit text default null
)
returns table (
    id              bigint,
    report_id       bigint,
    section_header  text,
    page_number     int,
    chunk_text      text,
    similarity      float
)
language sql stable
as $$
    select c.id, c.report_id, c.section_header, c.page_number, c.chunk_text,
           1 - (c.embedding <=> query_embedding) as similarity
    from chunks c
    join reports r on r.id = c.report_id
    where filter_permit is null or r.permit_number = filter_permit
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- NOTE: an ivfflat index on chunks.embedding speeds up search at scale
-- (tens of thousands+ chunks) but needs a meaningful number of rows to
-- tune itself well. At "high hundreds of reports" (low thousands of
-- chunks), a plain sequential scan is fast enough — skip this until
-- search feels slow:
--   create index on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
