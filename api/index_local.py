import os, io, re, sys
from dotenv import load_dotenv
from pypdf import PdfReader
from openai import OpenAI
import chromadb
from chromadb.config import Settings

load_dotenv(".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
COLLECTION = os.getenv("CHROMA_COLLECTION", "ksg_docs")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

client = OpenAI(api_key=OPENAI_API_KEY)

def chunk_text(text: str, max_chars=1200):
    text = re.sub(r"\s+", " ", text).strip()
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i+max_chars])
        i += max_chars
    return [c for c in out if len(c) > 80]

def chroma_collection():
    url = CHROMA_URL.replace("http://", "").replace("https://", "")
    host, port = url.split(":")
    c = chromadb.HttpClient(host=host, port=int(port), settings=Settings(allow_reset=False))
    return c.get_or_create_collection(name=COLLECTION)

def embed(texts):
    res = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in res.data]

def index_pdf(path: str):
    pdf_path = path
    filename = os.path.basename(pdf_path)
    doc_id = filename  # simple doc id for local MVP

    reader = PdfReader(pdf_path)
    col = chroma_collection()

    ids, docs, metas = [], [], []
    for page_no, page in enumerate(reader.pages, start=1):
        t = (page.extract_text() or "").strip()
        if len(t) < 50:
            continue
        for ci, ch in enumerate(chunk_text(t)):
            ids.append(f"{doc_id}-p{page_no}-c{ci}")
            docs.append(ch)
            metas.append({"filename": filename, "page": page_no, "source_url": f"local://{filename}"})

    if not ids:
        print("No text found to index.")
        return 0

    vecs = embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=vecs, metadatas=metas)
    return len(ids)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python index_local.py /path/to/file.pdf")
        sys.exit(1)
    n = index_pdf(sys.argv[1])
    print(f"✅ Indexed {n} chunks.")
