"""
Utility helpers: logging, safe JSON parsing, and simple LLM response caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths (project root = directory containing this file)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
EXTRACTED_IMAGES_DIR = PROJECT_ROOT / "extracted_images"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def ensure_directories() -> None:
    """Create standard folders if they do not exist."""
    EXTRACTED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger once (safe to call multiple times)."""
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# LLM cache (in-memory; keyed by hash of inputs + provider/model)
# ---------------------------------------------------------------------------
_llm_cache: dict[str, Any] = {}


def cache_key(
    inspection_text: str,
    thermal_text: str,
    image_filenames: list[str],
    provider: str,
    model: str,
) -> str:
    """Build a stable key for caching LLM responses."""
    payload = f"{provider}|{model}|{inspection_text}|{thermal_text}|{sorted(image_filenames)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_get(key: str) -> Optional[Any]:
    """Return cached value or None."""
    return _llm_cache.get(key)


def cache_set(key: str, value: Any) -> None:
    """Store value in cache (memory only; cleared on process exit)."""
    _llm_cache[key] = value


def clear_llm_cache() -> None:
    """Clear in-memory LLM cache (e.g. for testing)."""
    _llm_cache.clear()


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def safe_json_loads(text: str) -> Any:
    """Parse JSON from model output; strip common markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Drop first fence line and last fence if present
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def env_flag(name: str, default: str = "false") -> bool:
    """Read boolean-ish environment variable."""
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")

