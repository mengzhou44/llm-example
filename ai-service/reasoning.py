import json
from dataclasses import dataclass
from typing import Literal

import anthropic

_INTENT_SYSTEM = (
    "You are an intent analyzer. Analyze the user's message and return a JSON object with exactly these fields:\n"
    '- "requires_kb": true if the question is about personal information, uploaded documents, or topics '
    "likely covered in the user's personal documents; false for general knowledge questions\n"
    '- "complexity": "high" if the question requires deep multi-step reasoning, analysis, or synthesis; '
    '"low" for straightforward factual or conversational questions\n'
    '- "topic": a 2-5 word summary of what the question is about\n'
    '- "is_issue_analysis": true if the message is asking to diagnose, analyze, or summarize a problem, '
    "error, bug, support ticket, or incident description; false otherwise\n"
    "Return only raw JSON, no markdown fences, no extra text."
)

_COT_INSTRUCTION = (
    "\n\nBefore giving your final answer, briefly reason through the question step by step, "
    "then provide a clear, complete response."
)


@dataclass
class IntentResult:
    requires_kb: bool
    complexity: Literal["low", "high"]
    topic: str
    is_issue_analysis: bool = False


def _content_to_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


async def analyze_intent(
    message: str,
    history: list[dict],
    client: anthropic.AsyncAnthropic,
    model: str,
) -> IntentResult:
    """Return a structured intent analysis of the user's message. Defaults to safe values on failure."""
    recent = history[:-1][-4:]
    history_text = (
        "\n".join(
            f"{m['role'].upper()}: {_content_to_str(m['content'])[:200]}" for m in recent
        )
        if recent
        else "None"
    )
    user_content = f"Recent conversation:\n{history_text}\n\nCurrent message: {message}"
    try:
        result = await client.messages.create(
            model=model,
            max_tokens=100,
            system=_INTENT_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = result.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return IntentResult(
            requires_kb=bool(data.get("requires_kb", False)),
            complexity="high" if data.get("complexity") == "high" else "low",
            topic=str(data.get("topic", "")),
            is_issue_analysis=bool(data.get("is_issue_analysis", False)),
        )
    except Exception:
        return IntentResult(requires_kb=True, complexity="low", topic="", is_issue_analysis=False)


def validate_response(
    text: str,
    kb_used: bool,
    kb_results: list[dict],
    kb_documents: dict,
) -> bool:
    """Return True if the response passes quality checks."""
    if len(text.strip()) < 25:
        return False
    if kb_used and kb_results:
        doc_names = [
            kb_documents.get(c["doc_id"], {}).get("name", "")
            for c in kb_results
        ]
        if not any(name and name.lower() in text.lower() for name in doc_names):
            return False
    return True


def build_reasoning_prompt(base_prompt: str) -> str:
    return base_prompt + _COT_INSTRUCTION
