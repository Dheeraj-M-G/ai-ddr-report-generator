"""
LLM layer: structured DDR JSON from inspection + thermal text using OpenAI or Gemini.
Prompts are module-level constants for reuse and testing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Union

from utils import (
    cache_get,
    cache_key,
    cache_set,
    get_logger,
    safe_json_loads,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Reusable prompts (strict: no fabrication)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_DDR = """You are a senior building diagnostic assistant. Your job is to produce a structured JSON report from inspection and thermal PDF text (and optional image filenames).

STRICT RULES:
1. Never invent facts, measurements, locations, or issues not supported by the input text.
2. If something is not stated in the inputs, use the exact string "Not Available" for that field.
3. If inspection text and thermal text disagree on a fact, record it under "conflicts" and do not merge them into a single made-up statement.
4. Remove duplicate observations only when they clearly describe the same issue in the same area; otherwise keep separate rows.
5. Image filenames listed are only for reference—you must not claim you "saw" image pixels; map an image to an observation only when the text clearly ties that area/issue to a figure or when a filename clearly matches a section mentioned in text.
6. Output VALID JSON only matching the schema provided in the user message—no markdown, no commentary outside JSON."""

USER_PROMPT_TEMPLATE = """You will receive:
- INSPECTION_REPORT_TEXT: text extracted from the inspection PDF.
- THERMAL_REPORT_TEXT: text extracted from the thermal PDF.
- AVAILABLE_IMAGE_FILES: list of saved image filenames (basename only) from both PDFs. Use these strings exactly in "image_reference" when appropriate, or "Not Available".

Produce a single JSON object with this exact structure:
{{
  "property_issue_summary": "Short plain-language summary of main issues found in the sources, or Not Available",
  "observations": [
    {{
      "area": "location/room/zone or Not Available",
      "issue": "short label or Not Available",
      "description": "what the documents say, or Not Available",
      "thermal_observation": "thermal-related text for this area if present, else Not Available",
      "combined_insight": "neutral synthesis only from the two sources; Not Available if insufficient",
      "severity": "Low | Medium | High | Not Available (use Not Available if severity not stated)",
      "recommendation": "only if supported by text; else Not Available",
      "image_reference": "exact filename from AVAILABLE_IMAGE_FILES or Not Available"
    }}
  ],
  "probable_root_cause": "plain language; only if inferable from text—otherwise Not Available",
  "severity_assessment": {{
    "overall": "Low | Medium | High | Not Available",
    "reasoning": "brief reasoning tied only to stated facts, or Not Available"
  }},
  "recommended_actions": ["bullet-level strings in client-friendly language; empty array if none stated"],
  "additional_notes": "or Not Available",
  "missing_or_unclear": ["list strings describing gaps, unclear items, or Not Available"],
  "conflicts": [
    {{
      "topic": "short label",
      "inspection_says": "paraphrase from inspection text or Not Available",
      "thermal_says": "paraphrase from thermal text or Not Available"
    }}
  ]
}}

--- INSPECTION_REPORT_TEXT ---
{inspection_text}
--- END INSPECTION ---

--- THERMAL_REPORT_TEXT ---
{thermal_text}
--- END THERMAL ---

--- AVAILABLE_IMAGE_FILES (use exact basenames in image_reference when relevant) ---
{image_list}
--- END FILES ---
"""


def _default_ddr_structure() -> Dict[str, Any]:
    na = "Not Available"
    return {
        "property_issue_summary": na,
        "observations": [],
        "probable_root_cause": na,
        "severity_assessment": {"overall": na, "reasoning": na},
        "recommended_actions": [],
        "additional_notes": na,
        "missing_or_unclear": [na],
        "conflicts": [],
    }


def _call_openai(
    inspection_text: str,
    thermal_text: str,
    image_basenames: List[str],
    model: str,
) -> Dict[str, Any]:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in the environment.")

    client = OpenAI(api_key=api_key)

    user_content = USER_PROMPT_TEMPLATE.format(
        inspection_text=inspection_text[:120000],
        thermal_text=thermal_text[:120000],
        image_list=json.dumps(image_basenames),
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_DDR},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    raw = response.choices[0].message.content or "{}"
    data = safe_json_loads(raw)

    if not isinstance(data, dict):
        raise ValueError("Model returned non-object JSON")

    return data


def _call_gemini(
    inspection_text: str,
    thermal_text: str,
    image_basenames: List[str],
    model: str,
) -> Dict[str, Any]:

    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    user_content = USER_PROMPT_TEMPLATE.format(
        inspection_text=inspection_text[:120000],
        thermal_text=thermal_text[:120000],
        image_list=json.dumps(image_basenames),
    )

    full_prompt = SYSTEM_PROMPT_DDR + "\n\n" + user_content

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
        )

        raw = response.text

        data = safe_json_loads(raw)

        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure")

    except Exception as e:
        logger.error(f"Gemini failed: {e}")
        data = _default_ddr_structure()
        data["additional_notes"] = f"Gemini failed: {e}"

    return data


def generate_ddr_json(
    inspection_text: str,
    thermal_text: str,
    image_paths: List[Union[Path, str]],
    use_cache: bool = True,
) -> Dict[str, Any]:

    image_basenames = [Path(p).name for p in image_paths]

    provider = os.environ.get("DDR_LLM_PROVIDER", "openai").lower().strip()
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-1.0-pro")
    
    key = cache_key(
        inspection_text,
        thermal_text,
        image_basenames,
        provider,
        openai_model if provider == "openai" else gemini_model,
    )

    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            logger.info("LLM cache hit (key prefix=%s...)", key[:16])
            return cached

    try:
        if provider == "gemini":
            data = _call_gemini(
                inspection_text,
                thermal_text,
                image_basenames,
                gemini_model,
            )
        else:
            data = _call_openai(
                inspection_text,
                thermal_text,
                image_basenames,
                openai_model,
            )
    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        data = _default_ddr_structure()
        data["additional_notes"] = (
            f"Automated analysis could not be completed. Error: {e!s}. "
            "Sections below use placeholders."
        )
    else:
        logger.info("LLM call succeeded (%s)", provider)

    if use_cache:
        cache_set(key, data)

    return data
