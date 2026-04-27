import asyncio
import json
import os
import pathlib
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import anthropic
import numpy as np
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
CONTEXT_TOKEN_BUDGET = 7168
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MB

_BASE = pathlib.Path(__file__).parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
TEMPLATES: dict[str, str] = _prompts_config["templates"]

sessions: dict[str, list[dict]] = {}
session_locks: dict[str, asyncio.Lock] = {}

_embedding_model: SentenceTransformer | None = None
_model_lock = asyncio.Lock()
_kb_lock = asyncio.Lock()
kb_documents: dict[str, dict] = {}
kb_chunks: list[dict] = []


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _truncate_history(messages: list[dict]) -> list[dict]:
    """Drop oldest messages until history fits within CONTEXT_TOKEN_BUDGET."""
    total = sum(_estimate_tokens(m["content"]) for m in messages)
    while total > CONTEXT_TOKEN_BUDGET and len(messages) > 1:
        removed = messages.pop(0)
        total -= _estimate_tokens(removed["content"])
    return messages


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


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class StreamChatRequest(BaseModel):
    message: str
    session_id: str
    template: str = "helpful_assistant"


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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": request.message}],
    )

    return ChatResponse(response=message.content[0].text)


@app.post("/chat/stream")
async def chat_stream(request: StreamChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    system_prompt = TEMPLATES.get(request.template)
    if system_prompt is None:
        raise HTTPException(status_code=400, detail=f"Unknown template: {request.template}")

    lock = session_locks.setdefault(request.session_id, asyncio.Lock())
    async with lock:
        history = sessions.setdefault(request.session_id, [])
        history.append({"role": "user", "content": request.message})
        _truncate_history(history)

        if (
            len(history) == 1
            and _estimate_tokens(history[0]["content"]) > CONTEXT_TOKEN_BUDGET
        ):
            raise HTTPException(status_code=400, detail="Message too long")

        snapshot = list(history)

    return StreamingResponse(
        _stream_response(request.session_id, system_prompt, snapshot),
        media_type="text/event-stream",
    )


async def _stream_response(
    session_id: str, system_prompt: str, messages: list[dict]
) -> AsyncIterator[str]:
    accumulated = []

    async with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            accumulated.append(text)
            yield f"data: {json.dumps({'delta': text})}\n\n"

    full_response = "".join(accumulated)
    sessions[session_id].append({"role": "assistant", "content": full_response})

    yield "data: [DONE]\n\n"


@app.post("/knowledge/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    if not (file.filename or "").endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 1 MB limit")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

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


@app.get("/knowledge/documents", response_model=list[DocumentResponse])
async def list_documents():
    return [DocumentResponse(id=doc_id, **doc) for doc_id, doc in kb_documents.items()]


@app.delete("/knowledge/documents/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in kb_documents:
        raise HTTPException(status_code=404, detail="Document not found")
    async with _kb_lock:
        if doc_id not in kb_documents:
            raise HTTPException(status_code=404, detail="Document not found")
        del kb_documents[doc_id]
        kb_chunks[:] = [c for c in kb_chunks if c["doc_id"] != doc_id]
    return {"ok": True}


@app.post("/knowledge/search", response_model=list[SearchResult])
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
