import os
from typing import Tuple, List, Dict, Any

import chromadb


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _chroma_conn() -> tuple[str, int, bool]:
    """
    Supports either:
      - CHROMA_URL=https://ksg-chroma.onrender.com
    or:
      - CHROMA_HOST=ksg-chroma.onrender.com
      - CHROMA_PORT=443
      - CHROMA_SSL=true
    """

    url = (os.getenv("CHROMA_URL") or "").strip()
    if url:
        # very small parser to avoid extra deps
        ssl = url.startswith("https://")
        host = url.replace("https://", "").replace("http://", "")
        host = host.split("/")[0]
        # if URL includes :port
        if ":" in host:
            host_only, port_str = host.split(":", 1)
            host = host_only
            port = int(port_str)
        else:
            port = 443 if ssl else 80
        return host, port, ssl

    host = (os.getenv("CHROMA_HOST") or "localhost").strip()
    port = int((os.getenv("CHROMA_PORT") or "8000").strip())

    # If CHROMA_SSL is not set, infer it: port 443 => SSL
    ssl = _bool_env("CHROMA_SSL", default=(port == 443))

    return host, port, ssl


def get_chroma_client() -> chromadb.ClientAPI:
    host, port, ssl = _chroma_conn()

    # IMPORTANT: create the client only when needed
    # NOTE: chromadb.HttpClient supports ssl=bool
    return chromadb.HttpClient(host=host, port=port, ssl=ssl)


def query_index(question: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Minimal query: queries a Chroma collection named 'ksg'.
    Adjust collection name / metadata keys to match your indexing logic.
    """
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    res = col.query(
        query_texts=[question],
        n_results=3,
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    if not docs:
        return ("No results found in the vector store yet.", [])

    citations: List[Dict[str, Any]] = []
    for d, m in zip(docs, metas):
        citations.append({"text": d, "meta": m})

    # simple answer = top doc
    answer = docs[0]
    return answer, citations


def index_pdf(doc_uid: str, pdf_path: str) -> int:
    """
    Minimal stub: confirms connectivity + adds a placeholder entry.
    Replace with your real chunking/embedding logic later.
    """
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    col.add(
        ids=[doc_uid],
        documents=[f"Uploaded PDF stored at {pdf_path}"],
        metadatas=[{"doc_uid": doc_uid, "path": pdf_path}],
    )
    return 1
