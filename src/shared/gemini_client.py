"""Generate bilingual weekly commentary via Google Gemini API."""

from __future__ import annotations

import json
import logging

import httpx

from config import settings

log = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

_SYSTEM_PROMPT = """\
You write short, casual weekly dividend commentary for a personal finance blog \
called OpenWealthLab. The author is a private investor who publicly tracks their \
real portfolio dividends.

Rules:
- Write 2-4 sentences per language. Be conversational, not formal.
- If the week was strong (big gains, many payments), be enthusiastic.
- If the week was quiet (few or zero payments), be encouraging/chill.
- Use concrete numbers from the data (e.g. "47.82 € net", "+320%").
- Do NOT invent data not provided. Only reference the numbers given.
- Output valid JSON: {"en": "...", "de": "..."}
- No markdown formatting in the JSON values, just plain text with occasional emoji.
"""


def generate_commentary(
    current: dict,
    prev_week: dict,
    prev_year: dict,
    dividends: list[dict],
) -> dict[str, str]:
    """Call Gemini to produce ``{"en": "...", "de": "..."}`` commentary.

    Falls back to empty strings on error so the pipeline never breaks.
    """
    if not settings.GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set – skipping commentary generation.")
        return {"en": "", "de": ""}

    # Build a concise data summary for the prompt
    stocks = ", ".join(d.get("stock", "?") for d in dividends) if dividends else "none"
    user_prompt = (
        f"Week: {current['week']}\n"
        f"Stocks that paid: {stocks}\n"
        f"This week: {current['count']} payments, "
        f"gross={current['total_gross']}, net={current['total_net']}, tax={current['total_tax']}\n"
        f"Previous week ({prev_week['week']}): {prev_week['count']} payments, "
        f"gross={prev_week['total_gross']}, net={prev_week['total_net']}\n"
        f"Same week last year ({prev_year['week']}): {prev_year['count']} payments, "
        f"gross={prev_year['total_gross']}, net={prev_year['total_net']}\n"
    )

    body = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": settings.GEMINI_API_KEY},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        # Gemini 2.5 may return multiple parts (thinking + answer) — take the last text part
        parts = resp.json()["candidates"][0]["content"]["parts"]
        text = None
        for part in reversed(parts):
            if "text" in part:
                text = part["text"]
                break
        if not text:
            log.warning("Gemini returned no text parts.")
            return {"en": "", "de": ""}
        log.debug("Gemini raw response text: %s", text[:500])
        result = json.loads(text)
        log.info("Gemini commentary generated: EN=%d chars, DE=%d chars",
                 len(result.get("en", "")), len(result.get("de", "")))
        return {"en": result.get("en", ""), "de": result.get("de", "")}
    except Exception:
        log.exception("Gemini API call failed – using empty commentary.")
        return {"en": "", "de": ""}
