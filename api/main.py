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

# -----------------------------
# ✅ CORS (FIXES YOUR ERROR)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ksg-api.onrender.com",
        # later add: https://your-vercel-app.vercel.app
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Health
# -----------------------------
@app.get("/health")
def health():
    return {"ok": True}

# -----------------------------
# Auth
# -----------------------------
@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            name=payload.name.lower(),
            email=email,
            is_admin=True if email.endswith("@gmail.com") else False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = make_token(user.id, user.is_admin)

    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_admin": user.is_admin,
        },
    }

# -----------------------------
# Sessions
# -----------------------------
@app.post("/sessions")
def create_session(
    title: dict,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    s = ChatSession(user_id=user["sub"], title=title.get("title"))
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title}

# -----------------------------
# Chat
# -----------------------------
@app.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.add(Message(session_id=session.id, role="user", content=payload.message))
    db.commit()

    answer, citations = query_index(payload.message)

    db.add(Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return {
        "answer": answer,
        "citations": citations,
    }

# -----------------------------
# Admin: Upload + Index PDF
# -----------------------------
UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/admin/documents/upload")
def admin_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    if not user["adm"]:
        raise HTTPException(status_code=403, detail="Admin only")

    doc_uid = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{doc_uid}__{file.filename}")

    with open(path, "wb") as f:
        f.write(file.file.read())

    doc = Document(
        doc_uid=doc_uid,
        filename=file.filename,
        local_path=path,
        status="indexing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks = index_pdf(doc_uid, path)

    doc.status = "ready"
    db.commit()

    return {
        "ok": True,
        "document_id": doc.id,
        "doc_uid": doc_uid,
        "chunks_indexed": chunks,
    }

# -----------------------------
# Admin: Reindex
# -----------------------------
@app.post("/admin/documents/{doc_uid}/reindex")
def admin_reindex(
    doc_uid: str,
    db: Session = Depends(get_db),
    user=Depends(verify_token),
):
    if not user["adm"]:
        raise HTTPException(status_code=403, detail="Admin only")

    doc = db.query(Document).filter(Document.doc_uid == doc_uid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = index_pdf(doc_uid, doc.local_path)
    doc.status = "ready"
    db.commit()

    return {
        "ok": True,
        "doc_uid": doc_uid,
        "chunks_indexed": chunks,
    }
