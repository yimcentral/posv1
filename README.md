# Historical Staff Report Retrieval — Website Edition

Verbatim paragraph search over historical planning staff reports, deployed as a real website with no server for you to manage. No generative answers — every result is a real quote, mapped to permit number, address, and source PDF.

**Total ongoing cost at this scale: $0/month**, plus a few dollars one time to ingest your backlog (see Step 5).

## What you're setting up

Three free accounts, connected together:
1. **Supabase** — the database. Stores report metadata, searchable text, and the PDF files themselves.
2. **Anthropic** — the AI that reads each PDF once and pulls out the permit number/address/scope. (Or OpenRouter — see the note in Step 3.)
3. **Voyage AI** — the AI that turns text into "meaning vectors" so search understands intent, not just keywords.

Then **GitHub** (to hold the code) and **Streamlit Community Cloud** (to run it as a public website) — both free, both point-and-click, no command line required.

Do these in order. Each step is short.

---

### Step 1 — Create your Supabase project

1. Go to supabase.com, sign up (free), click **New Project**.
2. Pick any name/region, set a database password (save it somewhere — you likely won't need it again, but keep it).
3. Once the project finishes spinning up, go to the **SQL Editor** tab (left sidebar).
4. Click **New Query**, open the `supabase_setup.sql` file from this project, copy its entire contents, paste it in, and click **Run**. This creates the tables and the search function.
5. Go to **Storage** (left sidebar) → **New bucket** → name it exactly `staff-reports` → toggle **Public bucket** ON (fine here since these are public records) → **Create**.
6. Go to **Project Settings → API**. Copy two values, you'll need them in Step 6:
   - **Project URL** → this is `SUPABASE_URL` ygycsqimkotlbhzsqjli
   - **service_role key** (not the "anon" key) → this is `SUPABASE_KEY` eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlneWNzcWlta290bGJoenNxamxpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTI2NDUzNSwiZXhwIjoyMTA0ODQwNTM1fQ._P_HSgpojtTyuLbYfnBZq4BKOnLcaLirX-5OqwS0skE

### Step 2 — Get an Anthropic API key

1. Go to console.anthropic.com, sign up, add a small amount of credit (a few dollars covers your whole backlog — see cost note below).
2. Go to **API Keys** → **Create Key**. Copy it; this is `ANTHROPIC_API_KEY`.

*(If you'd rather use OpenRouter instead — e.g. you already have credit there — sign up at openrouter.ai, create a key, and in Step 6 set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY=...` instead of the Anthropic key. Everything else is identical.)*

### Step 3 — Get a Voyage AI key

1. Go to voyageai.com, sign up, go to **API Keys**, create one. Copy it; this is `VOYAGE_API_KEY`.
2. You will not be charged for this at your corpus size — the free tier (200 million tokens/month) is far larger than a few hundred staff reports will ever use.

### Step 4 — Put the code on GitHub (no command line needed)

1. Go to github.com, sign up, click the **+** in the top right → **New repository**. Name it `staff-report-search`, keep it **Private**, click **Create repository**.
2. On the new repo page, click **uploading an existing file**.
3. Drag in every file from this project folder (`app.py`, `config.py`, `db.py`, `embeddings.py`, `extraction.py`, `ingest.py`, `search.py`, `requirements.txt`, `supabase_setup.sql`, `README.md`) — you do not need to upload `supabase_setup.sql` for the app to run, but keep it in the repo so you have it on hand.
4. Scroll down, click **Commit changes**.

### Step 5 — Deploy on Streamlit Community Cloud

1. Go to share.streamlit.io, sign in with your GitHub account, click **Create app**.
2. Pick your `staff-report-search` repo, branch `main`, main file path `app.py`.
3. Before clicking Deploy, click **Advanced settings** → **Secrets**, and paste in (fill in your real values):

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your service_role key"
ANTHROPIC_API_KEY = "sk-ant-..."
VOYAGE_API_KEY = "your voyage key"
```

4. Click **Deploy**. In a minute or two you'll get a public URL like `https://staff-report-search.streamlit.app` — that's your website. Bookmark it, share it with staff.

### Step 6 — Load your reports

1. Open your new website, go to the **Admin / Ingest** tab.
2. Upload a small test batch first (5–10 PDFs), click **Run ingestion now**, confirm they show up correctly in the table below with the right permit number/address.
3. Once that looks right, upload the rest of your backlog. There's no strict limit on batch size, but if you have hundreds of files, doing it in a few batches of 50–100 is easier to watch for errors than one giant batch.
4. Each month going forward: open the site, Admin tab, upload the new batch, done. No coding, no redeployment — the website and database are permanent, only the data grows.

---

## What this costs, concretely

- **Ingesting your full backlog (one time)**: at Haiku pricing, expect roughly $2–8 total for "high hundreds" of reports. Check your Anthropic console usage after the test batch in Step 6 to confirm your actual per-document cost before running the rest.
- **Ongoing monthly batches**: cents.
- **Voyage embeddings**: $0 — you won't get near the free tier ceiling.
- **Supabase**: $0 on the free tier (500MB database, 1GB file storage — plenty for text + PDFs at this scale; if your corpus is very PDF-heavy you may eventually outgrow the storage tier, at which point Supabase's paid tier starts around $25/month).
- **Streamlit Community Cloud**: $0.
- **GitHub**: $0 (private repos are free).

## If something breaks

- **"Can't reach the database" on the site**: check the Secrets in Streamlit Cloud settings match your Supabase Project URL and service_role key exactly.
- **Ingestion says "skipped (no extractable text)"**: that PDF is a scanned image with no text layer — pypdf can't read it. This needs OCR, which isn't built in; flag how many of your reports are scans before assuming full coverage.
- **A file won't upload during ingestion**: two reports can't share the exact same filename in this setup (the app uses filename as the storage path) — rename duplicates before uploading.
- **Search returns nothing**: confirm the Admin tab shows chunks > 0. If it's 0, ingestion silently failed — check the Anthropic/Voyage keys are valid and have available credit.

## Known limitations (same as the underlying design, not the hosting)

- **Section-header detection** is a text-pattern heuristic, not a true layout parser — it'll misfire on reports with inconsistent formatting across departments or years. If mislabeled sections turn out to matter, the fix is a layout-aware extractor, not a bigger model.
- **Scanned PDFs are not supported** without adding OCR — see above.
- **No authentication** — matches the brief (public record, no PII, no access tiering needed). If you ever need to restrict who can search, that has to be added deliberately; don't assume the current Streamlit password login is enough on its own for anything sensitive.
