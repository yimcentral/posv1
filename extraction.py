"""
Phase 1 core logic: turn a PDF into (metadata, chunks).

Two things happen here, and they are deliberately kept separate:
1. Deterministic text extraction + chunking (pypdf) — no LLM involved,
   fully reproducible, this is what gets stored and displayed verbatim.
2. LLM metadata extraction — only used to populate permit_number /
   project_address / scope_summary fields. It never touches the stored
   chunk text. If the LLM call fails, ingestion still proceeds with
   NULL metadata rather than blocking the batch.
"""
import json
import re

from pypdf import PdfReader

import config

# Provider is selected once at import time via config.LLM_PROVIDER.
# Both branches expose a call_llm(prompt) -> str function so the rest
# of this file doesn't care which one is active.
if config.LLM_PROVIDER == "openrouter":
    import os as _os
    from openai import OpenAI
    _client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_os.environ["OPENROUTER_API_KEY"],
    )

    def call_llm(prompt: str) -> str:
        resp = _client.chat.completions.create(
            model=config.EXTRACTION_MODEL,  # e.g. "anthropic/claude-haiku-4.5"
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
else:
    from anthropic import Anthropic
    _client = Anthropic()  # reads ANTHROPIC_API_KEY from env

    def call_llm(prompt: str) -> str:
        resp = _client.messages.create(
            model=config.EXTRACTION_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

# Heuristic for "looks like a section header": short line, mostly caps,
# or ends in a colon. This is intentionally simple — staff reports vary
# in format and a fancier layout-aware parser (e.g. using font size from
# pdfplumber) is a natural Phase 1.5 upgrade if header quality matters.
_HEADER_RE = re.compile(r"^(?:[A-Z0-9][A-Z0-9 \-/&,.]{2,60}:?|.{3,60}:)$")


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Returns a list of page texts (index 0 = page 1). Takes raw PDF
    bytes rather than a file path, since uploaded files never touch
    local disk in the hosted version."""
    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [page.extract_text() or "" for page in reader.pages]


def looks_like_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 70:
        return False
    if _HEADER_RE.match(line) and not line.endswith("."):
        return True
    return False


def chunk_pages(pages: list[str]):
    """
    Splits page text into paragraph-level chunks, tracking the nearest
    preceding section header and originating page number.

    Yields dicts: {chunk_index, section_header, page_number, chunk_text}
    """
    chunks = []
    current_header = None
    buffer = ""
    buffer_page = 1

    def flush():
        nonlocal buffer
        text = buffer.strip()
        if text:
            chunks.append({
                "section_header": current_header,
                "page_number": buffer_page,
                "chunk_text": text,
            })
        buffer = ""

    for page_num, page_text in enumerate(pages, start=1):
        for raw_line in page_text.split("\n"):
            line = raw_line.strip()
            if not line:
                # blank line = paragraph break
                flush()
                buffer_page = page_num
                continue
            if looks_like_header(line):
                flush()
                current_header = line.rstrip(":")
                buffer_page = page_num
                continue
            if not buffer:
                buffer_page = page_num
            buffer += (" " if buffer else "") + line
            if len(buffer) > config.MAX_CHUNK_CHARS:
                flush()
    flush()

    # Merge chunks that are too short into the following chunk so search
    # results aren't a page full of one-line fragments.
    merged = []
    carry = None
    for c in chunks:
        if carry is not None:
            c = {
                **c,
                "chunk_text": carry["chunk_text"] + " " + c["chunk_text"],
                "section_header": carry["section_header"] or c["section_header"],
                "page_number": carry["page_number"],
            }
            carry = None
        if len(c["chunk_text"]) < config.MIN_CHUNK_CHARS:
            carry = c
            continue
        merged.append(c)
    if carry is not None:
        merged.append(carry)

    for i, c in enumerate(merged):
        c["chunk_index"] = i
    return merged


_EXTRACTION_PROMPT = """You are extracting structured metadata from a city \
planning department staff report. Read the text below and return ONLY a \
JSON object (no markdown fences, no commentary) with exactly these keys:

- "permit_number": the permit, case, or project number as printed (string, or null if not found)
- "project_address": the project's street address (string, or null if not found)
- "scope_summary": a one-to-two sentence neutral summary of the scope of work described (string, or null if not found)

Do not invent values. If a field is genuinely not present in the text, use null.

REPORT TEXT:
---
{text}
---
"""


def extract_metadata_via_llm(pages: list[str]) -> dict:
    text = "\n\n".join(pages[:config.EXTRACTION_MAX_PAGES])
    text = text[:12000]  # guard against pathologically dense pages

    try:
        raw = call_llm(_EXTRACTION_PROMPT.format(text=text))
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        return {
            "permit_number": data.get("permit_number"),
            "project_address": data.get("project_address"),
            "scope_summary": data.get("scope_summary"),
        }
    except Exception as e:
        # Ingestion must not halt on a single bad extraction. Flag it
        # loudly in the metadata itself so it's easy to find and fix by hand.
        return {
            "permit_number": None,
            "project_address": None,
            "scope_summary": f"[EXTRACTION FAILED: {e}]",
        }
