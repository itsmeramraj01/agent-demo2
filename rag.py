"""Retrieval over the Wanderly policy knowledge base (cancellation, baggage, insurance).

Docs are chunked by markdown heading and embedded with Voyage AI. Claude is given
a `search_travel_policies` tool and decides for itself when to call it (agentic RAG)
instead of every prompt being force-fed the whole knowledge base.

Knowledge base source of truth is `knowledge_base/*.md`. If a blob has been
uploaded to Vercel Blob for a given filename (recorded in
`knowledge_base/blob_manifest.json`, see knowledge_base/blob_manifest.json for
the "how to upload" note), that copy is fetched instead, so the KB content can
be updated by re-uploading to Blob without a redeploy. Local files are always
the fallback.
"""

import json
import os
import re
import urllib.request
from pathlib import Path

import voyageai

KB_DIR = Path(__file__).resolve().parent / "knowledge_base"
MANIFEST_PATH = KB_DIR / "blob_manifest.json"
VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-4-lite")

SEARCH_POLICIES_TOOL = {
    "name": "search_travel_policies",
    "description": (
        "Search Wanderly's travel policy knowledge base (cancellation, baggage, "
        "and travel insurance policies) for passages relevant to a question. "
        "Use this whenever a traveler asks about, or their notes mention, "
        "cancellations, refunds, baggage allowances or fees, or travel insurance, "
        "instead of guessing at policy details."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The traveler's question or topic to search for, in plain English.",
            }
        },
        "required": ["query"],
    },
}

_index_cache = None  # (chunks, embeddings), built lazily and reused for the process lifetime


def _voyage_client() -> "voyageai.Client":
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key or api_key == "your_voyage_api_key_here":
        raise RuntimeError(
            "VOYAGE_API_KEY is not set. Add it to config.env "
            "(get a key at https://dashboard.voyageai.com/)."
        )
    return voyageai.Client(api_key=api_key)


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _read_blob(url: str) -> str:
    # The KB lives in a private Blob store, so reads need an auth header - Vercel
    # accepts either a short-lived VERCEL_OIDC_TOKEN (set automatically on Vercel)
    # or the static BLOB_READ_WRITE_TOKEN (set in config.env / Vercel env vars).
    token = os.environ.get("VERCEL_OIDC_TOKEN") or os.environ.get("BLOB_READ_WRITE_TOKEN")
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310 - fixed https blob URLs only
        return resp.read().decode("utf-8")


def _load_documents() -> list[tuple[str, str]]:
    manifest = _load_manifest()
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        blob_url = manifest.get(path.name)
        text = None
        if blob_url:
            try:
                text = _read_blob(blob_url)
            except Exception:
                text = None  # fall back to the bundled local copy below
        if text is None:
            text = path.read_text(encoding="utf-8")
        docs.append((path.name, text))
    return docs


def _chunk_markdown(source: str, text: str) -> list[dict]:
    """Split a doc into chunks on '##' headings, one chunk per section."""
    sections = re.split(r"\n(?=##\s)", text.strip())
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"#{1,2}\s*(.+)", section)
        heading = heading_match.group(1).strip() if heading_match else source
        chunks.append({"source": source, "heading": heading, "text": section})
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _build_index():
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    chunks = []
    for source, text in _load_documents():
        chunks.extend(_chunk_markdown(source, text))

    if not chunks:
        _index_cache = ([], [])
        return _index_cache

    client = _voyage_client()
    result = client.embed([c["text"] for c in chunks], model=VOYAGE_MODEL, input_type="document")
    _index_cache = (chunks, result.embeddings)
    return _index_cache


def search_policies(query: str, top_k: int = 3) -> str:
    """Embeds `query` with Voyage and returns the top matching KB passages as text,
    formatted for use as a tool_result block."""
    chunks, embeddings = _build_index()
    if not chunks:
        return "The policy knowledge base is empty or unavailable right now."

    client = _voyage_client()
    query_embedding = client.embed([query], model=VOYAGE_MODEL, input_type="query").embeddings[0]

    scored = sorted(
        zip(chunks, embeddings),
        key=lambda pair: _cosine(query_embedding, pair[1]),
        reverse=True,
    )[:top_k]

    return "\n\n---\n\n".join(
        f"[{chunk['source']} — {chunk['heading']}]\n{chunk['text']}" for chunk, _ in scored
    )
