"""Shared Claude API caller used by all nodes."""

import os, json, anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    return _client


def call_claude(system: str, user: str, max_tokens: int = 1024) -> dict | None:
    """
    Call Claude and parse the JSON response.
    Returns parsed dict or None if API key missing / parse fails.
    """
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return None

    try:
        msg = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown fences if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"[LLM ERR] {e}")
        return None
