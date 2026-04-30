import asyncio
import json
import logging
import os
import pathlib
from typing import AsyncIterator

import anthropic
import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from reasoning import analyze_intent, build_reasoning_prompt, validate_response
from routers.knowledge import _cosine_sim, _get_embedding_model, _kb_lock, kb_chunks, kb_documents
from tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

router = APIRouter()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = os.getenv("MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
CONTEXT_TOKEN_BUDGET = int(os.getenv("CONTEXT_TOKEN_BUDGET", "7168"))
ENABLE_VALIDATION = os.getenv("ENABLE_VALIDATION", "true").lower() == "true"
THINKING_BUDGET_TOKENS = int(os.getenv("THINKING_BUDGET_TOKENS", "2000"))

_BASE = pathlib.Path(__file__).parent.parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
TEMPLATES: dict[str, str] = _prompts_config["templates"]

sessions: dict[str, list[dict]] = {}
session_locks: dict[str, asyncio.Lock] = {}

KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
KB_MIN_SCORE = float(os.getenv("KB_MIN_SCORE", "0.35"))

# Errors that warrant a single retry — transient API/network issues.
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


def _error_code(exc: Exception) -> str:
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(exc, anthropic.InternalServerError):
        return "server_error"
    if isinstance(exc, anthropic.APIConnectionError):
        return "connection_error"
    if isinstance(exc, anthropic.AuthenticationError):
        return "auth_error"
    if isinstance(exc, anthropic.BadRequestError):
        return "bad_request"
    return "unknown"


def _error_events(exc: Exception) -> list[str]:
    """Return the two terminal SSE event strings for a Claude API error."""
    logger.error("Claude API error: %s: %s", type(exc).__name__, exc)
    payload = {"error": {"code": _error_code(exc), "message": str(exc)}}
    return [f"data: {json.dumps(payload)}\n\n", "data: [DONE]\n\n"]


def _content_to_str(content) -> str:
    """Flatten a content field (str or list of blocks) to plain text."""
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

    return StreamingResponse(
        _stream_response(request.session_id, system_prompt, request.message, snapshot),
        media_type="text/event-stream",
    )


async def _stream_response(
    session_id: str,
    base_system_prompt: str,
    message: str,
    messages: list[dict],
) -> AsyncIterator[str]:
    # === Intent Analysis ===
    yield f"data: {json.dumps({'step': 'analyzing'})}\n\n"
    intent = await analyze_intent(message, messages, client, MODEL)
    logger.info("session=%s intent: requires_kb=%s complexity=%s topic=%r",
                session_id, intent.requires_kb, intent.complexity, intent.topic)

    # === RAG Routing ===
    kb_results: list[dict] = []
    if intent.requires_kb and kb_chunks:
        kb_results = await _search_kb(message, history=messages)
    source = "both" if kb_results else "general_ai"
    yield f"data: {json.dumps({'source': source})}\n\n"

    # === Build System Prompt (KB context + chain-of-thought) ===
    system_prompt = base_system_prompt
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
    system_prompt = build_reasoning_prompt(system_prompt)

    # === First Stream (with optional extended thinking for high complexity) ===
    accumulated_text: list[str] = []
    first_message = None
    high_complexity = intent.complexity == "high"
    # messages_for_retry tracks the effective history used if quality-validation retry fires;
    # updated to include tool-use turns when they occur.
    messages_for_retry = messages

    call_kwargs: dict = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS + (THINKING_BUDGET_TOKENS if high_complexity else 0),
        "system": system_prompt,
        "messages": messages,
        "tools": TOOLS,
    }
    if high_complexity:
        call_kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}

    try:
        async with client.messages.stream(**call_kwargs) as stream:
            async for text in stream.text_stream:
                accumulated_text.append(text)
                yield f"data: {json.dumps({'delta': text})}\n\n"
            first_message = await stream.get_final_message()
    except anthropic.BadRequestError:
        # Model does not support extended thinking — fall back to CoT prompt only.
        call_kwargs.pop("thinking", None)
        call_kwargs["max_tokens"] = MAX_TOKENS
        accumulated_text = []
        try:
            async with client.messages.stream(**call_kwargs) as stream:
                async for text in stream.text_stream:
                    accumulated_text.append(text)
                    yield f"data: {json.dumps({'delta': text})}\n\n"
                first_message = await stream.get_final_message()
        except _RETRYABLE as exc:
            yield f"data: {json.dumps({'step': 'retrying_api'})}\n\n"
            try:
                accumulated_text = []
                async with client.messages.stream(**call_kwargs) as stream:
                    async for text in stream.text_stream:
                        accumulated_text.append(text)
                        yield f"data: {json.dumps({'delta': text})}\n\n"
                    first_message = await stream.get_final_message()
            except Exception as exc2:
                for chunk in _error_events(exc2):
                    yield chunk
                return
        except Exception as exc:
            for chunk in _error_events(exc):
                yield chunk
            return
    except _RETRYABLE as exc:
        yield f"data: {json.dumps({'step': 'retrying_api'})}\n\n"
        try:
            accumulated_text = []
            async with client.messages.stream(**call_kwargs) as stream:
                async for text in stream.text_stream:
                    accumulated_text.append(text)
                    yield f"data: {json.dumps({'delta': text})}\n\n"
                first_message = await stream.get_final_message()
        except Exception as exc2:
            for chunk in _error_events(exc2):
                yield chunk
            return
    except Exception as exc:
        for chunk in _error_events(exc):
            yield chunk
        return

    # === Tool-Use Loop ===
    if first_message and first_message.stop_reason == "tool_use":
        tool_use_blocks = [b for b in first_message.content if b.type == "tool_use"]

        extended = list(messages) + [
            {
                "role": "assistant",
                "content": [_serialize_content_block(b) for b in first_message.content],
            }
        ]

        tool_results = []
        for block in tool_use_blocks:
            yield f"data: {json.dumps({'tool_call': {'name': block.name, 'input': block.input}})}\n\n"
            logger.info("session=%s tool_call: %s input=%s", session_id, block.name, block.input)
            result = await execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        extended.append({"role": "user", "content": tool_results})
        messages_for_retry = extended

        accumulated_text = []
        tool_stream_kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=extended,
        )
        try:
            async with client.messages.stream(**tool_stream_kwargs) as stream2:
                async for text in stream2.text_stream:
                    accumulated_text.append(text)
                    yield f"data: {json.dumps({'delta': text})}\n\n"
        except _RETRYABLE as exc:
            yield f"data: {json.dumps({'step': 'retrying_api'})}\n\n"
            try:
                accumulated_text = []
                async with client.messages.stream(**tool_stream_kwargs) as stream2:
                    async for text in stream2.text_stream:
                        accumulated_text.append(text)
                        yield f"data: {json.dumps({'delta': text})}\n\n"
            except Exception as exc2:
                for chunk in _error_events(exc2):
                    yield chunk
                return
        except Exception as exc:
            for chunk in _error_events(exc):
                yield chunk
            return

        sessions[session_id].extend([
            {
                "role": "assistant",
                "content": [_serialize_content_block(b) for b in first_message.content],
            },
            {"role": "user", "content": tool_results},
        ])

    # === Validation and Retry ===
    full_text = "".join(accumulated_text)
    if ENABLE_VALIDATION:
        yield f"data: {json.dumps({'step': 'validating'})}\n\n"
        if not validate_response(full_text, bool(kb_results), kb_results, kb_documents):
            yield f"data: {json.dumps({'step': 'retrying'})}\n\n"
            retry_prompt = system_prompt + (
                "\n\nIMPORTANT: Your previous response was inadequate. "
                "Provide a complete, detailed response that fully answers the question."
            )
            if kb_results:
                retry_prompt += " Cite the source documents by name."
            accumulated_text = []
            quality_retry_kwargs = dict(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=retry_prompt,
                messages=messages_for_retry,
            )
            try:
                async with client.messages.stream(**quality_retry_kwargs) as retry_stream:
                    async for text in retry_stream.text_stream:
                        accumulated_text.append(text)
                        yield f"data: {json.dumps({'delta': text})}\n\n"
            except _RETRYABLE as exc:
                yield f"data: {json.dumps({'step': 'retrying_api'})}\n\n"
                try:
                    accumulated_text = []
                    async with client.messages.stream(**quality_retry_kwargs) as retry_stream:
                        async for text in retry_stream.text_stream:
                            accumulated_text.append(text)
                            yield f"data: {json.dumps({'delta': text})}\n\n"
                except Exception as exc2:
                    for chunk in _error_events(exc2):
                        yield chunk
                    return
            except Exception as exc:
                for chunk in _error_events(exc):
                    yield chunk
                return
            full_text = "".join(accumulated_text)

    sessions[session_id].append({"role": "assistant", "content": full_text})
    logger.info("session=%s response complete, length=%d chars", session_id, len(full_text))
    yield "data: [DONE]\n\n"
