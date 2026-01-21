from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os, uuid, shutil

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

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/login")
def login(payload: dict):
    name = payload.get("name") or ""
    email = payload.get("email") or ""
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # TEMP rule: make admins by email domain (adjust later)
    is_admin = email.lower().endswith("@ksg.go.ke")

    token = make_token(name=name, email=email, is_admin=is_admin)
    return {"token": token, "user": {"name": name, "email": email, "is_admin": is_admin}}

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
