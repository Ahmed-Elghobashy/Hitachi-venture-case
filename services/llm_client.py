from __future__ import annotations

import json
import logging
import os
import re
from typing import List, Optional

from config.portfolio_config import GEMINI_API_KEY_ENV, GEMINI_MODEL, LLM_HTML_CHAR_LIMIT

logger = logging.getLogger(__name__)

_client: Optional["genai.Client"] = None


def _get_client() -> Optional["genai.Client"]:
    global _client
    if _client is not None:
        return _client
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        logger.warning("LLM client unavailable: %s", exc)
        return None
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        logger.warning("LLM client missing API key")
        return None
    _client = genai.Client(api_key=api_key)
    return _client


def gemini_healthcheck() -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents="Return a JSON array with one string: OK",
        )
    except Exception as exc:
        logger.warning("LLM healthcheck failed error=%s", exc)
        return False
    try:
        parsed = json.loads(response.text or "")
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("LLM healthcheck parse failed error=%s raw_text=%s", exc, response.text)
        return False
    ok = isinstance(parsed, list) and len(parsed) == 1 and str(parsed[0]).strip().upper() == "OK"
    if ok:
        logger.info("LLM healthcheck OK")
    else:
        logger.warning("LLM healthcheck unexpected response parsed=%s", parsed)
    return ok


def extract_company_names_with_gemini(html: str) -> List[str]:
    client = _get_client()
    if not client:
        return []
    trimmed_html = html[:LLM_HTML_CHAR_LIMIT]
    prompt = (
        "Extract company names from the HTML below. "
        "Return a JSON array of unique company names as strings, no extra text.\n\n"
        f"HTML:\n{trimmed_html}"
    )
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        logger.warning("LLM extraction failed error=%s", exc)
        return []
    raw_text = (response.text or "").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()
    try:
        names = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("LLM response parse failed error=%s raw_text=%s", exc, response.text)
        return []
    if not isinstance(names, list):
        logger.warning("LLM response not a list type=%s", type(names).__name__)
        return []
    cleaned = []
    seen = set()
    for name in names:
        if not isinstance(name, str):
            continue
        cleaned_name = re.sub(r"\s+", " ", name).strip()
        if 2 <= len(cleaned_name) <= 60:
            key = cleaned_name.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(cleaned_name)
    if cleaned:
        logger.info("LLM extracted %s names: %s", len(cleaned), ", ".join(cleaned))
    return cleaned


def llm_matches_energy(description: str, keywords: List[str]) -> bool:
    client = _get_client()
    if not client:
        return False
    prompt = (
        "Decide if the company description is relevant to energy investing. "
        "Keywords: "
        f"{', '.join(keywords)}. "
        "Return a JSON boolean only.\n\n"
        f"Description:\n{description}"
    )
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        logger.warning("LLM filter failed error=%s", exc)
        return False
    raw_text = (response.text or "").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()
    try:
        parsed = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("LLM filter parse failed error=%s raw_text=%s", exc, response.text)
        return False
    if isinstance(parsed, bool):
        return parsed
    logger.warning("LLM filter response not boolean value=%s", parsed)
    return False


def llm_filter_energy_bulk(descriptions: List[str], keywords: List[str]) -> List[bool]:
    if not descriptions:
        return []
    client = _get_client()
    if not client:
        return [False] * len(descriptions)
    prompt = (
        "You will receive a JSON array of company descriptions. "
        "For each description, decide if it is relevant to energy investing. "
        f"Keywords: {', '.join(keywords)}. "
        "Return a JSON array of booleans with the same length and order, no extra text.\n\n"
        f"Descriptions:\n{json.dumps(descriptions)}"
    )
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        logger.warning("LLM bulk filter failed error=%s", exc)
        return [False] * len(descriptions)
    raw_text = (response.text or "").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()
    try:
        parsed = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("LLM bulk filter parse failed error=%s raw_text=%s", exc, response.text)
        return [False] * len(descriptions)
    if not isinstance(parsed, list) or len(parsed) != len(descriptions):
        logger.warning("LLM bulk filter unexpected response length=%s", len(parsed) if isinstance(parsed, list) else "n/a")
        return [False] * len(descriptions)
    results: List[bool] = []
    for item in parsed:
        results.append(bool(item) if isinstance(item, bool) else False)
    return results
