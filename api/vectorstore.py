import os
from typing import List, Tuple, Dict, Any

import chromadb
from pypdf import PdfReader

# ---- Chroma client ----
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
collection = client.get_or_create_collection(name="ksg_docs")


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    text = " ".join(text.split())
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def index_pdf(doc_uid: str, pdf_path: str) -> int:
    """
    Extract text from a PDF and store chunks in Chroma.
    IDs are unique by (doc_uid + chunk index), so reindex replaces existing.
    Returns number of chunks indexed.
    """
    reader = PdfReader(pdf_path)

    # delete old chunks for this doc_uid (if any)
    # Chroma doesn't have delete-by-metadata in all modes, so we query ids then delete.
    existing = collection.get(where={"doc_uid": doc_uid}, include=["metadatas", "documents", "ids"])
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])

    all_chunks = []
    metadatas = []
    ids = []

    for page_index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        for chunk_index, chunk in enumerate(_chunk_text(page_text), start=1):
            chunk_id = f"{doc_uid}::p{page_index}::c{chunk_index}"
            ids.append(chunk_id)
            all_chunks.append(chunk)
            metadatas.append(
                {
                    "doc_uid": doc_uid,
                    "page": page_index,
                    "chunk": chunk_index,
                    "source": os.path.basename(pdf_path),
                }
            )

    if all_chunks:
        collection.add(ids=ids, documents=all_chunks, metadatas=metadatas)

    return len(all_chunks)


def query_index(question: str, n_results: int = 6) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Very simple retrieval-only answer:
    - fetch top chunks from Chroma
    - return them as a "context" answer + citations

    Later we’ll upgrade this to LLM answering (OpenAI) using the retrieved context.
    """
    res = collection.query(query_texts=[question], n_results=n_results)

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    if not docs:
        return (
            "I don’t have enough indexed content yet to answer that. Please upload/reindex documents first.",
            [],
        )

    citations = []
    context_lines = []
    for d, m in zip(docs, metas):
        context_lines.append(f"- {d}")
        citations.append(
            {
                "filename": m.get("source", ""),
                "page": m.get("page", None),
                "doc_uid": m.get("doc_uid", ""),
            }
        )

    answer = "Here’s what I found in the indexed documents:\n\n" + "\n\n".join(context_lines)
    return answer, citations
