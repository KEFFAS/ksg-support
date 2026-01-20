from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os, uuid, shutil

from db import SessionLocal, engine, Base
import models  # IMPORTANT: registers models with Base
from auth import make_token, verify_token
from vectorstore import index_pdf, query_index

app = FastAPI(title="KSG Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/login")
def login(payload: dict, db: Session = Depends(get_db)):
    name = payload.get("name")
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    token, user = make_token(db, name=name, email=email)
    return {"token": token, "user": user}

@app.post("/chat")
def chat(payload: dict, user=Depends(verify_token)):
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")

    answer, citations = query_index(message)
    return {"answer": answer, "citations": citations}

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/admin/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    doc_uid = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{doc_uid}.pdf")

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks = index_pdf(doc_uid, path)

    return {"ok": True, "doc_uid": doc_uid, "chunks_indexed": chunks}
