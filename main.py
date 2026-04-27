import asyncio
import json
import os
import pathlib
from typing import AsyncIterator

import anthropic
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
CONTEXT_TOKEN_BUDGET = 7168

_BASE = pathlib.Path(__file__).parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
TEMPLATES: dict[str, str] = _prompts_config["templates"]

sessions: dict[str, list[dict]] = {}
session_locks: dict[str, asyncio.Lock] = {}


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
