import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

load_dotenv(".env")

CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
COLLECTION = os.getenv("CHROMA_COLLECTION", "ksg_docs")

def get_collection():
    # CHROMA_URL like http://localhost:8000
    url = CHROMA_URL.replace("http://", "").replace("https://", "")
    host, port = url.split(":")
    client = chromadb.HttpClient(host=host, port=int(port), settings=Settings(allow_reset=False))
    return client.get_or_create_collection(name=COLLECTION)
