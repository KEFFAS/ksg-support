from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uuid
import os

from db import get_db
from models import User, Session as ChatSession, Message, Document
from auth import make_token, verify_token
from schemas import LoginRequest, ChatRequest
from vectorstore import index_pdf, query_index

app = FastAPI(title="KSG Support API")

# ✅ CORS (fixes browser fetch failures)
# NOTE: we include localhost + allow any vercel preview URL using regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    name = (payload.name or "").strip().lower() or "user"

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # First user becomes admin (simple bootstrap)
        is_admin = db.query(User).count() == 0
        user = User(name=name, email=email, is_admin=is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = make_token(user.id, user.is_admin)
    return {
        "token": token,
        "user": {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin},
    }

@app.post("/sessions")
def create_session(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    title = (payload.get("title") or "New session").strip()
    s = ChatSession(user_id=int(user["sub"]), title=title)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title}

@app.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == payload.session_id, ChatSession.user_id == int(user["sub"]))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.add(Message(session_id=session.id, role="user", content=payload.message))
    db.commit()

    answer, citations = query_index(payload.message)

    db.add(Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return {"answer": answer, "citations": citations}


UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/admin/documents/upload")
def admin_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    if not user.get("adm"):
        raise HTTPException(status_code=403, detail="Admin only")

    doc_uid = str(uuid.uuid4())
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(UPLOAD_DIR, f"{doc_uid}__{safe_name}")

    with open(path, "wb") as f:
        f.write(file.file.read())

    doc = Document(
        doc_uid=doc_uid,
        filename=safe_name,
        local_path=path,
        status="indexing",
        storage_url=None,  # nullable in your DB now
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks = index_pdf(doc_uid, path)

    doc.status = "ready"
    db.commit()

    return {"ok": True, "document_id": doc.id, "doc_uid": doc_uid, "chunks_indexed": chunks}

@app.post("/admin/documents/{doc_uid}/reindex")
def admin_reindex(
    doc_uid: str,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    if not user.get("adm"):
        raise HTTPException(status_code=403, detail="Admin only")

    doc = db.query(Document).filter(Document.doc_uid == doc_uid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = index_pdf(doc_uid, doc.local_path)
    doc.status = "ready"
    db.commit()

    return {"ok": True, "doc_uid": doc_uid, "chunks_indexed": chunks}
