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

from routers.knowledge import _cosine_sim, _get_embedding_model, _kb_lock, kb_chunks, kb_documents
from tools import TOOLS, execute_tool

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


def _content_to_str(content) -> str:
    """Flatten a content field (str or list of blocks) to plain text for routing/search."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _estimate_tokens(content) -> int:
    return len(_content_to_str(content)) // 4


def _truncate_history(messages: list[dict]) -> list[dict]:
    """Drop oldest messages until history fits within CONTEXT_TOKEN_BUDGET."""
    total = sum(_estimate_tokens(m["content"]) for m in messages)
    while total > CONTEXT_TOKEN_BUDGET and len(messages) > 1:
        removed = messages.pop(0)
        total -= _estimate_tokens(removed["content"])
    return messages


def _serialize_content_block(block) -> dict:
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


async def _classify_query(message: str, history: list[dict]) -> bool:
    """Return True if the query warrants KB retrieval; defaults to True on failure."""
    async with _kb_lock:
        doc_names = [doc["name"] for doc in kb_documents.values()]
    doc_list = ", ".join(doc_names) if doc_names else "none"

    recent = history[:-1][-4:]
    history_text = (
        "\n".join(
            f"{m['role'].upper()}: {_content_to_str(m['content'])[:200]}" for m in recent
        )
        if recent
        else "None"
    )

    system = (
        "You are a query router. Decide if the user's question needs a knowledge base lookup.\n"
        "Reply with exactly one word: YES or NO.\n"
        "Say YES if the question is about personal information, uploaded documents, or topics "
        "likely covered in the available documents.\n"
        "Say NO if the question is general knowledge that doesn't require personal context."
    )
    user_content = (
        f"Available documents: {doc_list}\n"
        f"Recent conversation:\n{history_text}\n"
        f"Current question: {message}"
    )

    try:
        result = await client.messages.create(
            model=MODEL,
            max_tokens=5,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return result.content[0].text.strip().upper().startswith("Y")
    except Exception:
        return True


async def _search_kb(query: str, history: list[dict] | None = None) -> list[dict]:
    if not kb_chunks:
        return []
    if history:
        prior_user = [
            m["content"] for m in history[:-1]
            if m["role"] == "user" and isinstance(m["content"], str)
        ][-2:]
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

    use_kb = await _classify_query(request.message, snapshot) if kb_chunks else False
    kb_results = await _search_kb(request.message, history=snapshot) if use_kb else []
    source = "both" if kb_results else "general_ai"

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
        _stream_response(request.session_id, system_prompt, snapshot, source),
        media_type="text/event-stream",
    )


async def _stream_response(
    session_id: str, system_prompt: str, messages: list[dict], source: str
) -> AsyncIterator[str]:
    yield f"data: {json.dumps({'source': source})}\n\n"
    accumulated_text = []

    # First call — stream text deltas and detect tool use
    async with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
        tools=TOOLS,
    ) as stream:
        async for text in stream.text_stream:
            accumulated_text.append(text)
            yield f"data: {json.dumps({'delta': text})}\n\n"
        first_message = await stream.get_final_message()

    if first_message.stop_reason == "tool_use":
        tool_use_blocks = [b for b in first_message.content if b.type == "tool_use"]

        # Extend message history with the assistant's tool-use turn
        extended = list(messages) + [
            {
                "role": "assistant",
                "content": [_serialize_content_block(b) for b in first_message.content],
            }
        ]

        # Execute each tool and collect results
        tool_results = []
        for block in tool_use_blocks:
            yield f"data: {json.dumps({'tool_call': {'name': block.name, 'input': block.input}})}\n\n"
            result = await execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        extended.append({"role": "user", "content": tool_results})

        # Second call — stream the final answer
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=extended,
        ) as stream2:
            async for text in stream2.text_stream:
                accumulated_text.append(text)
                yield f"data: {json.dumps({'delta': text})}\n\n"

        # Persist tool-use context in session history for follow-up turns
        sessions[session_id].extend([
            {
                "role": "assistant",
                "content": [_serialize_content_block(b) for b in first_message.content],
            },
            {"role": "user", "content": tool_results},
        ])

    sessions[session_id].append({"role": "assistant", "content": "".join(accumulated_text)})
    yield "data: [DONE]\n\n"
