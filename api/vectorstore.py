# api/vectorstore.py (only the client part)
import os
import chromadb

def _chroma_settings():
    host = os.getenv("CHROMA_HOST", "localhost").strip()
    port = int(os.getenv("CHROMA_PORT", "8000").strip())
    ssl = os.getenv("CHROMA_SSL", "false").lower() in ("1", "true", "yes")
    return host, port, ssl

def get_chroma_client() -> chromadb.ClientAPI:
    host, port, ssl = _chroma_settings()
    # chromadb supports ssl= in HttpClient (newer versions)
    return chromadb.HttpClient(host=host, port=port, ssl=ssl)
