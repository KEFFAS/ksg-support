import os
from typing import Tuple, List, Dict, Any
from urllib.parse import urlparse

import chromadb


def _parse_chroma() -> tuple[str, int, bool]:
    """
    Supports either:
      - CHROMA_URL=https://ksg-chroma.onrender.com
    OR:
      - CHROMA_HOST=ksg-chroma.onrender.com
      - CHROMA_PORT=443
      - CHROMA_SSL=true
    """
    url = (os.getenv("CHROMA_URL") or "").strip()
    if url:
        u = urlparse(url)
        host = u.hostname or "localhost"
        ssl = (u.scheme == "https")
        port = u.port or (443 if ssl else 80)
        return host, int(port), ssl

    host = (os.getenv("CHROMA_HOST") or "localhost").strip()
    port = int((os.getenv("CHROMA_PORT") or "8000").strip())
    ssl = (os.getenv("CHROMA_SSL") or "").strip().lower() in ("1", "true", "yes", "y")
    return host, port, ssl


def get_chroma_client() -> chromadb.ClientAPI:
    host, port, ssl = _parse_chroma()
    # IMPORTANT: ssl=True makes requests go over https (fixes your Cloudflare 400)
    # Chroma HttpClient supports ssl=... :contentReference[oaicite:1]{index=1}
    return chromadb.HttpClient(host=host, port=port, ssl=ssl)


def query_index(question: str) -> Tuple[str, List[Dict[str, Any]]]:
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    res = col.query(query_texts=[question], n_results=3)

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    if not docs:
        return ("No results found in the vector store yet.", [])

    citations: List[Dict[str, Any]] = []
    for d, m in zip(docs, metas):
        citations.append({"text": d, "meta": m})

    return docs[0], citations


def index_pdf(doc_uid: str, pdf_path: str) -> int:
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    # placeholder entry (replace with real chunking later)
    col.add(
        ids=[doc_uid],
        documents=[f"Uploaded PDF stored at {pdf_path}"],
        metadatas=[{"doc_uid": doc_uid, "path": pdf_path}],
    )
    return 1
