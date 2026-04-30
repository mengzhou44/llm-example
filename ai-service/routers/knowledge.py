import asyncio
import io
import logging
import os
import pathlib
import re
import uuid
from datetime import datetime, timezone

import numpy as np
from docx import Document
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")

# Folder where uploaded documents are persisted so they survive restarts.
KB_DOCS_DIR = pathlib.Path(__file__).parent.parent / "kb_docs"
KB_DOCS_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ValueError(f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must be less than CHUNK_SIZE ({CHUNK_SIZE})")

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
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        return []

    # Any sentence longer than CHUNK_SIZE gets character-split first
    normalized: list[str] = []
    for s in sentences:
        if len(s) <= CHUNK_SIZE:
            normalized.append(s)
        else:
            for i in range(0, len(s), CHUNK_SIZE - CHUNK_OVERLAP):
                normalized.append(s[i : i + CHUNK_SIZE])

    chunks: list[str] = []
    current: list[str] = []

    for sentence in normalized:
        if current and len(" ".join(current) + " " + sentence) > CHUNK_SIZE:
            chunks.append(" ".join(current))
            # Carry forward tail sentences up to CHUNK_OVERLAP chars as overlap
            overlap: list[str] = []
            for s in reversed(current):
                trial = " ".join([s] + overlap)
                if len(trial) > CHUNK_OVERLAP:
                    break
                overlap.insert(0, s)
            current = overlap
        current.append(sentence)

    if current:
        chunks.append(" ".join(current))

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


async def preload_kb_from_disk() -> None:
    """Load all documents from KB_DOCS_DIR into memory on startup."""
    files = sorted(
        f for f in KB_DOCS_DIR.iterdir()
        if f.is_file() and f.suffix in ALLOWED_EXTENSIONS
    )
    if not files:
        return
    logger.info("Preloading %d document(s) from %s", len(files), KB_DOCS_DIR)
    for path in files:
        try:
            content = path.read_bytes()
            text = _extract_text(path.name, content)
            if not text.strip():
                continue
            chunks = _chunk_text(text)
            model = await _get_embedding_model()
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(None, lambda: model.encode(chunks))
            doc_id = str(uuid.uuid4())
            uploaded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            async with _kb_lock:
                for chunk_val, embedding in zip(chunks, embeddings):
                    kb_chunks.append({"doc_id": doc_id, "text": chunk_val, "embedding": embedding})
                kb_documents[doc_id] = {
                    "name": path.name,
                    "uploaded_at": uploaded_at,
                    "chunk_count": len(chunks),
                }
            logger.info("Preloaded: %s (%d chunks)", path.name, len(chunks))
        except Exception as exc:
            logger.warning("Failed to preload %s: %s", path.name, exc)


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

    (KB_DOCS_DIR / file.filename).write_bytes(content)

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
        doc_name = kb_documents.pop(doc_id)["name"]
        kb_chunks[:] = [c for c in kb_chunks if c["doc_id"] != doc_id]

    disk_path = KB_DOCS_DIR / doc_name
    if disk_path.exists():
        disk_path.unlink()

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
