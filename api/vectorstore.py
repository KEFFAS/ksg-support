import os
from typing import Tuple, List, Dict, Any

import chromadb
from chromadb.config import Settings


def _chroma_settings() -> tuple[str, int, bool]:
    host = os.getenv("CHROMA_HOST", "").strip() or "localhost"
    port_str = os.getenv("CHROMA_PORT", "").strip() or "8000"
    ssl_str = os.getenv("CHROMA_SSL", "").strip().lower()
    ssl = ssl_str in ("1", "true", "yes", "y", "on")
    return host, int(port_str), ssl


def get_chroma_client() -> chromadb.ClientAPI:
    host, port, ssl = _chroma_settings()

    # IMPORTANT: When going through Cloudflare/Render, you must use HTTPS
    # so set ssl=True for port 443.
    return chromadb.HttpClient(
        host=host,
        port=port,
        settings=Settings(chroma_server_ssl_enabled=ssl),
    )


def query_index(question: str) -> Tuple[str, List[Dict[str, Any]]]:
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    res = col.query(query_texts=[question], n_results=3)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    if not docs:
        return ("No results found in the vector store yet.", [])

    citations = [{"text": d, "meta": m} for d, m in zip(docs, metas)]
    return docs[0], citations


def index_pdf(doc_uid: str, pdf_path: str) -> int:
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    col.add(
        ids=[doc_uid],
        documents=[f"Uploaded PDF stored at {pdf_path}"],
        metadatas=[{"doc_uid": doc_uid, "path": pdf_path}],
    )
    return 1
