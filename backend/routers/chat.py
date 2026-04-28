import asyncio
import json
import os
import pathlib
from typing import AsyncIterator

import anthropic
import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.knowledge import _cosine_sim, _get_embedding_model, kb_chunks, kb_documents

router = APIRouter()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = os.getenv("MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
CONTEXT_TOKEN_BUDGET = int(os.getenv("CONTEXT_TOKEN_BUDGET", "7168"))

_BASE = pathlib.Path(__file__).parent.parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
TEMPLATES: dict[str, str] = _prompts_config["templates"]

sessions: dict[str, list[dict]] = {}
session_locks: dict[str, asyncio.Lock] = {}

KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
KB_MIN_SCORE = float(os.getenv("KB_MIN_SCORE", "0.35"))


async def _search_kb(query: str, history: list[dict] | None = None) -> list[dict]:
    if not kb_chunks:
        return []
    # Enrich the query with recent prior user messages so follow-up questions
    # ("tell me more", "elaborate on that") still retrieve the right chunks.
    if history:
        prior_user = [m["content"] for m in history[:-1] if m["role"] == "user"][-2:]
        if prior_user:
            query = " ".join(prior_user) + " " + query
    model = await _get_embedding_model()
    loop = asyncio.get_running_loop()
    query_emb = await loop.run_in_executor(None, lambda: model.encode([query])[0])
    scored = sorted(
        [(_cosine_sim(query_emb, c["embedding"]), c) for c in kb_chunks],
        key=lambda x: x[0],
        reverse=True,
    )
    return [
        {"score": round(score, 3), "doc_id": c["doc_id"], "text": c["text"]}
        for score, c in scored[:KB_TOP_K]
        if score >= KB_MIN_SCORE
    ]


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _truncate_history(messages: list[dict]) -> list[dict]:
    """Drop oldest messages until history fits within CONTEXT_TOKEN_BUDGET."""
    total = sum(_estimate_tokens(m["content"]) for m in messages)
    while total > CONTEXT_TOKEN_BUDGET and len(messages) > 1:
        removed = messages.pop(0)
        total -= _estimate_tokens(removed["content"])
    return messages


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class StreamChatRequest(BaseModel):
    message: str
    session_id: str
    template: str = "helpful_assistant"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": request.message}],
    )

    return ChatResponse(response=message.content[0].text)


@router.post("/chat/stream")
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

    kb_results = await _search_kb(request.message, history=snapshot)
    if kb_results:
        excerpts = "\n\n".join(
            f"[Source: {kb_documents.get(c['doc_id'], {}).get('name', 'document')} | relevance: {c['score']:.2f}]\n{c['text']}"
            for c in kb_results
        )
        system_prompt = (
            f"{system_prompt}\n\n"
            "<knowledge_base_context>\n"
            "Use the following excerpts to answer the user's question. "
            "Cite the source document by name when drawing from it. "
            "If the context does not fully address the question, acknowledge what is and isn't covered.\n\n"
            f"{excerpts}\n"
            "</knowledge_base_context>"
        )

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
