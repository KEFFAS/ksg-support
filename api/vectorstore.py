import os
from typing import Tuple, List, Dict, Any

import chromadb


def _chroma_settings() -> tuple[str, int]:
    host = os.getenv("CHROMA_HOST", "").strip() or "localhost"
    port_str = os.getenv("CHROMA_PORT", "").strip() or "8000"
    return host, int(port_str)


def get_chroma_client() -> chromadb.ClientAPI:
    host, port = _chroma_settings()
    # IMPORTANT: create the client only when needed
    return chromadb.HttpClient(host=host, port=port)


def query_index(question: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Minimal stub: queries a Chroma collection named 'ksg'.
    Adjust collection name / metadata keys to match your indexing logic.
    """
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    # NOTE: this is basic. Your real logic may use embeddings, filters, etc.
    res = col.query(
        query_texts=[question],
        n_results=3,
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    # build a simple answer
    if not docs:
        return ("No results found in the vector store yet.", [])

    citations = []
    for d, m in zip(docs, metas):
        citations.append({"text": d, "meta": m})

    answer = docs[0]
    return answer, citations


def index_pdf(doc_uid: str, pdf_path: str) -> int:
    """
    Minimal stub: you likely already have chunking logic elsewhere.
    For now, this just confirms connectivity + creates the collection.
    """
    client = get_chroma_client()
    col = client.get_or_create_collection("ksg")

    # You probably have real chunking logic in another file (rag.py/indexer.py).
    # For now, just store one placeholder entry so you can verify end-to-end.
    col.add(
        ids=[doc_uid],
        documents=[f"Uploaded PDF stored at {pdf_path}"],
        metadatas=[{"doc_uid": doc_uid, "path": pdf_path}],
    )
    return 1
