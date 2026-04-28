import json
import os
import pathlib

import anthropic
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = os.getenv("MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

_BASE = pathlib.Path(__file__).parent.parent
with open(_BASE / "prompts.yaml") as f:
    _prompts_config = yaml.safe_load(f)
_SYSTEM_PROMPT: str = _prompts_config["issue_analyzer"]


class AnalyzeRequest(BaseModel):
    description: str


class AnalyzeResponse(BaseModel):
    summary: str
    root_cause: str
    suggestion: str


@router.post("/analyze/issue", response_model=AnalyzeResponse)
async def analyze_issue(request: AnalyzeRequest):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    message = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": request.description}],
    )

    try:
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            raw = raw.rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return AnalyzeResponse(
            summary=data["summary"],
            root_cause=data["root_cause"],
            suggestion=data["suggestion"],
        )
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"AI returned unexpected format: {e}")
