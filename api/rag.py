import os
from dotenv import load_dotenv
from openai import OpenAI
from vector import get_collection

load_dotenv(".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-nano-2025-08-07")

def embed_query(text: str):
    res = client.embeddings.create(model=EMBED_MODEL, input=[text])
    return res.data[0].embedding

def retrieve(query: str, k: int = 5):
    col = get_collection()
    q_emb = embed_query(query)
    res = col.query(
        query_embeddings=[q_emb],
        n_results=k,
        include=["documents", "metadatas"]
    )
    hits = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    for d, m in zip(docs, metas):
        hits.append({"text": d, "meta": m})
    return hits

def answer_with_context(question: str, hits):
    context = "\n\n".join(
        f"{h['meta'].get('filename','?')} (page {h['meta'].get('page','?')}):\n{h['text']}"
        for h in hits
    )

    prompt = f"""You are a Kenya School of Government customer support assistant.
Use the context to answer. If you use context, cite filename and page.
If the context is not enough, say you don't know.

Context:
{context}

Question:
{question}
"""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()
