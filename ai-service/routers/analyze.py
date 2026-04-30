import json
import logging
import os
import pathlib
import re

import anthropic
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.mock_tickets import _TICKETS

logger = logging.getLogger(__name__)

router = APIRouter()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = os.getenv("MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)

_BASE = pathlib.Path(__file__).parent.parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
_SYSTEM_PROMPT: str = _prompts_config["issue_analyzer"]

_TICKET_ID_RE = re.compile(r'\b(\d{3,6})\b')


def _resolve_description(text: str) -> tuple[str, str | None]:
    """Return (content_to_analyze, ticket_id_or_None).

    If the input looks like a ticket ID reference, fetch and format the ticket.
    Otherwise return the raw text unchanged.
    """
    match = _TICKET_ID_RE.search(text)
    if match:
        ticket_id = match.group(1)
        ticket = _TICKETS.get(ticket_id)
        if ticket:
            parts = [
                f"Title: {ticket['title']}",
                f"Status: {ticket['status']}",
                f"Priority: {ticket['priority']}",
                f"Description: {ticket['description']}",
            ]
            if ticket.get("resolution"):
                parts.append(f"Resolution: {ticket['resolution']}")
            return "\n".join(parts), ticket_id
    return text, None


class AnalyzeRequest(BaseModel):
    description: str


class AnalyzeResponse(BaseModel):
    summary: str
    root_cause: str
    suggestion: str
    ticket_id: str | None = None


@router.post("/analyze/issue", response_model=AnalyzeResponse)
async def analyze_issue(request: AnalyzeRequest):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    content, ticket_id = _resolve_description(request.description.strip())

    call_kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    try:
        message = await client.messages.create(**call_kwargs)
    except _RETRYABLE as exc:
        logger.warning("analyze_issue: retryable error on first attempt: %s", exc)
        try:
            message = await client.messages.create(**call_kwargs)
        except Exception as exc2:
            logger.error("analyze_issue: retry also failed: %s", exc2)
            raise HTTPException(status_code=503, detail=f"AI service unavailable: {exc2}") from exc2
    except anthropic.AuthenticationError as exc:
        logger.error("analyze_issue: auth error: %s", exc)
        raise HTTPException(status_code=502, detail="AI service authentication failed") from exc
    except Exception as exc:
        logger.error("analyze_issue: unexpected error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    try:
        block = message.content[0] if message.content else None
        raw = (getattr(block, "text", "") or "").strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            raw = raw.rsplit("```", 1)[0].strip()
        if not raw:
            raise ValueError("empty response from model")
        data = json.loads(raw)
        return AnalyzeResponse(
            summary=data["summary"],
            root_cause=data["root_cause"],
            suggestion=data["suggestion"],
            ticket_id=ticket_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI returned unexpected format: {e}")
