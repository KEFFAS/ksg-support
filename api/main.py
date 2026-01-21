from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import uuid
import shutil

from db import SessionLocal, engine, Base
import models  # IMPORTANT: registers models with Base
from auth import make_token, verify_token
from vectorstore import index_pdf, query_index

app = FastAPI(title="KSG Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup (simple for now)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"ok": True, "service": "KSG Support API"}


@app.get("/health")
def health():
    return {"ok": True}




@app.post("/auth/login")
def login(payload: dict):
    name = payload.get("name")
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    token, user = make_token(name=name, email=email)
    return {"token": token, "user": user}

@app.post("/chat")
def chat(payload: dict, user=Depends(verify_token)):
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")

    try:
        answer, citations = query_index(message)
        return {"answer": answer, "citations": citations}
    except Exception as e:
        # Don’t crash the API; return a clean error the frontend can handle
        raise HTTPException(
            status_code=503,
            detail=f"Vector store unavailable: {str(e)}",
        )


UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/admin/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    doc_uid = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{doc_uid}.pdf")

    try:
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    try:
        chunks = index_pdf(doc_uid, path)
    except Exception as e:
        # File is saved, but indexing failed (often Chroma connectivity)
        raise HTTPException(
            status_code=503,
            detail=f"Uploaded but indexing failed (vector store unavailable): {str(e)}",
        )

    return {"ok": True, "doc_uid": doc_uid, "chunks_indexed": chunks}
