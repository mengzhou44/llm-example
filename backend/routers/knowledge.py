import asyncio
import io
import os
import uuid
from datetime import datetime, timezone

import numpy as np
from docx import Document
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

router = APIRouter()

ALLOWED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

_embedding_model: SentenceTransformer | None = None
_model_lock = asyncio.Lock()
_kb_lock = asyncio.Lock()
kb_documents: dict[str, dict] = {}
kb_chunks: list[dict] = []


def _extract_text(filename: str, content: bytes) -> str:
    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if filename.endswith(".docx"):
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return content.decode("utf-8")


def _chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


async def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    async with _model_lock:
        if _embedding_model is None:
            loop = asyncio.get_running_loop()
            _embedding_model = await loop.run_in_executor(
                None, lambda: SentenceTransformer("all-MiniLM-L6-v2")
            )
    return _embedding_model


class DocumentResponse(BaseModel):
    id: str
    name: str
    uploaded_at: str
    chunk_count: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    doc_id: str
    doc_name: str
    text: str
    score: float


@router.post("/knowledge/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only .txt, .md, .pdf, and .docx files are supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    try:
        text = _extract_text(file.filename, content)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty or contains no extractable text")

    chunks = _chunk_text(text)
    model = await _get_embedding_model()
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(None, lambda: model.encode(chunks))

    doc_id = str(uuid.uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()

    async with _kb_lock:
        for chunk_val, embedding in zip(chunks, embeddings):
            kb_chunks.append({"doc_id": doc_id, "text": chunk_val, "embedding": embedding})
        kb_documents[doc_id] = {
            "name": file.filename,
            "uploaded_at": uploaded_at,
            "chunk_count": len(chunks),
        }

    return DocumentResponse(
        id=doc_id,
        name=file.filename,
        uploaded_at=uploaded_at,
        chunk_count=len(chunks),
    )


@router.get("/knowledge/documents", response_model=list[DocumentResponse])
async def list_documents():
    return [DocumentResponse(id=doc_id, **doc) for doc_id, doc in kb_documents.items()]


@router.delete("/knowledge/documents/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in kb_documents:
        raise HTTPException(status_code=404, detail="Document not found")
    async with _kb_lock:
        if doc_id not in kb_documents:
            raise HTTPException(status_code=404, detail="Document not found")
        del kb_documents[doc_id]
        kb_chunks[:] = [c for c in kb_chunks if c["doc_id"] != doc_id]
    return {"ok": True}


@router.post("/knowledge/search", response_model=list[SearchResult])
async def search_knowledge(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not kb_chunks:
        return []

    model = await _get_embedding_model()
    loop = asyncio.get_running_loop()
    query_emb = await loop.run_in_executor(
        None, lambda: model.encode([request.query])[0]
    )

    scored = sorted(
        [(_cosine_sim(query_emb, c["embedding"]), c) for c in kb_chunks],
        key=lambda x: x[0],
        reverse=True,
    )

    results = []
    for score, c in scored[: request.top_k]:
        doc = kb_documents.get(c["doc_id"])
        if doc is None:
            continue
        results.append(
            SearchResult(doc_id=c["doc_id"], doc_name=doc["name"], text=c["text"], score=score)
        )
    return results
