import os, re
from dotenv import load_dotenv
from pypdf import PdfReader
from openai import OpenAI
from vector import get_collection

load_dotenv(".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

def chunk_text(text: str, max_chars=1200):
    text = re.sub(r"\s+", " ", text).strip()
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i+max_chars])
        i += max_chars
    return [c for c in out if len(c) > 80]

def embed(texts):
    res = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in res.data]

def index_pdf_file(filepath: str, doc_id: str, filename: str, source_url: str):
    reader = PdfReader(filepath)
    col = get_collection()

    ids, docs, metas = [], [], []
    for page_no, page in enumerate(reader.pages, start=1):
        t = (page.extract_text() or "").strip()
        if len(t) < 50:
            continue
        for ci, ch in enumerate(chunk_text(t)):
            ids.append(f"{doc_id}-p{page_no}-c{ci}")
            docs.append(ch)
            metas.append({"doc_id": doc_id, "filename": filename, "page": page_no, "source_url": source_url})

    if not ids:
        return 0

    vecs = embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=vecs, metadatas=metas)
    return len(ids)
