import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session

from db import SessionLocal
from models import User, Session as ChatSession, Message, Document
from auth import make_token, verify_token
from rag import retrieve, answer_with_context
from indexer import index_pdf_file

load_dotenv(".env")

app = FastAPI(title="KSG Support API")

ADMIN_EMAILS = set(
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
)

UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_pdfs")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------
# DB + Auth helpers
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1].strip()
    data = verify_token(token)
    if not data:
        raise HTTPException(401, "Invalid token")
    return data


def ensure_session_access(db: Session, user_id: int, is_admin: bool, session_id: int):
    s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Session not found")
    if (not is_admin) and s.user_id != user_id:
        raise HTTPException(403, "Access denied")
    return s


# ---------------------------
# Public endpoints
# ---------------------------
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/login")
def login(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    if not name or not email:
        raise HTTPException(400, "Name and email required")

    is_admin = email in ADMIN_EMAILS

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(name=name, email=email, is_admin=is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # upgrade admin if allowlisted
        if is_admin and not user.is_admin:
            user.is_admin = True
            db.commit()

    token = make_token(user.id, user.is_admin)
    return {
        "token": token,
        "user": {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin},
    }


@app.post("/sessions")
def create_session(payload: dict, me=Depends(auth_user), db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip() or "New Session"
    s = ChatSession(user_id=me["user_id"], title=title)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title}


@app.get("/sessions")
def list_sessions(me=Depends(auth_user), db: Session = Depends(get_db)):
    q = db.query(ChatSession)
    if not me["is_admin"]:
        q = q.filter(ChatSession.user_id == me["user_id"])
    rows = q.order_by(ChatSession.created_at.desc()).limit(100).all()
    return [{"id": r.id, "title": r.title, "created_at": str(r.created_at), "user_id": r.user_id} for r in rows]


@app.get("/sessions/{session_id}/messages")
def list_messages(session_id: int, me=Depends(auth_user), db: Session = Depends(get_db)):
    ensure_session_access(db, me["user_id"], me["is_admin"], session_id)
    rows = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id).all()
    return [{"role": r.role, "content": r.content, "created_at": str(r.created_at)} for r in rows]


@app.post("/chat")
def chat(payload: dict, me=Depends(auth_user), db: Session = Depends(get_db)):
    session_id = int(payload.get("session_id") or 0)
    text = (payload.get("message") or "").strip()
    if not session_id or not text:
        raise HTTPException(400, "session_id and message are required")

    ensure_session_access(db, me["user_id"], me["is_admin"], session_id)

    # store user message
    db.add(Message(session_id=session_id, role="user", content=text))
    db.commit()

    # RAG retrieval + answer
    hits = retrieve(text, k=5)
    answer = answer_with_context(text, hits)

    db.add(Message(session_id=session_id, role="assistant", content=answer))
    db.commit()

    # De-duplicate + sort citations
    seen = set()
    citations = []
    for h in hits:
        fn = h["meta"].get("filename")
        pg = h["meta"].get("page")
        url = h["meta"].get("source_url")
        key = (fn, pg, url)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"filename": fn, "page": pg, "source_url": url})

    def _page_num(x):
        try:
            return int(x.get("page") or 0)
        except Exception:
            return 0

    citations.sort(key=lambda x: (x.get("filename") or "", _page_num(x)))

    # Filter citations to only those mentioned in the answer text
    answer_lc = answer.lower()
    filtered = []
    for c in citations:
        fn_lc = (c.get("filename") or "").lower()
        pg = str(c.get("page") or "").strip()
        if not fn_lc or not pg:
            continue
        if fn_lc in answer_lc and pg in answer_lc:
            filtered.append(c)

    # fallback: if nothing matched, return top 3 citations
    if not filtered:
        filtered = citations[:3]

    return {"answer": answer, "citations": filtered}


# ---------------------------
# Admin endpoints
# ---------------------------
@app.get("/admin/documents")
def admin_list_documents(me=Depends(auth_user), db: Session = Depends(get_db)):
    if not me["is_admin"]:
        raise HTTPException(403, "Admin only")
    rows = db.query(Document).order_by(Document.uploaded_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "doc_uid": r.doc_uid,
            "filename": r.filename,
            "status": r.status,
            "uploaded_at": str(r.uploaded_at),
        }
        for r in rows
    ]


@app.post("/admin/documents/upload")
def admin_upload_and_index(file: UploadFile = File(...), me=Depends(auth_user), db: Session = Depends(get_db)):
    if not me["is_admin"]:
        raise HTTPException(403, "Admin only")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF files only")

    doc_uid = str(uuid.uuid4())
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest_path = os.path.join(UPLOAD_DIR, f"{doc_uid}__{safe_name}")

    # Save file locally (MVP)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())

    doc = Document(
        doc_uid=doc_uid,
        filename=safe_name,
        local_path=dest_path,
        storage_url=None,  # nullable in DB for MVP
        status="indexing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        n = index_pdf_file(dest_path, doc_id=doc_uid, filename=safe_name, source_url=f"local://{safe_name}")
        doc.status = "indexed"
        db.commit()
        return {"ok": True, "document_id": doc.id, "doc_uid": doc_uid, "chunks_indexed": n}
    except Exception as e:
        doc.status = "failed"
        db.commit()
        raise HTTPException(500, f"Indexing failed: {e}")


@app.post("/admin/documents/{doc_uid}/reindex")
def admin_reindex(doc_uid: str, me=Depends(auth_user), db: Session = Depends(get_db)):
    if not me["is_admin"]:
        raise HTTPException(403, "Admin only")

    doc = db.query(Document).filter(Document.doc_uid == doc_uid).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.local_path or not os.path.exists(doc.local_path):
        raise HTTPException(400, "Local file not found for this document (MVP limitation).")

    doc.status = "indexing"
    db.commit()

    try:
        n = index_pdf_file(doc.local_path, doc_id=doc_uid, filename=doc.filename, source_url=f"local://{doc.filename}")
        doc.status = "indexed"
        db.commit()
        return {"ok": True, "doc_uid": doc_uid, "chunks_indexed": n}
    except Exception as e:
        doc.status = "failed"
        db.commit()
        raise HTTPException(500, f"Reindex failed: {e}")
