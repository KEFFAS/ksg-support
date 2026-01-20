from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=False)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    doc_uid = Column(String, unique=True, nullable=False, index=True)   # stable ID for vectors
    filename = Column(String, nullable=False)
    local_path = Column(String, nullable=True)   # for MVP local storage
    storage_url = Column(String, nullable=True)  # for future S3/R2
    status = Column(String, default="uploaded")  # uploaded/indexing/indexed/failed
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
