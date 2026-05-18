"""章节标题候选 + 书籍简介管理"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_agents.book.paths import BIBLE_DIR, REVIEWS_DIR, titles_path

SYNOPSIS_FILE = BIBLE_DIR / "marketing_synopsis.md"


def save_titles(chapter: int, candidates: list[dict[str, Any]]) -> Path:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    p = titles_path(chapter)
    p.write_text(
        json.dumps({"chapter": chapter, "candidates": candidates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


def load_titles(chapter: int) -> list[dict[str, Any]]:
    p = titles_path(chapter)
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text(encoding="utf-8")).get("candidates", []))
    except Exception:
        return []


def save_synopsis(text: str) -> Path:
    SYNOPSIS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNOPSIS_FILE.write_text(text, encoding="utf-8")
    return SYNOPSIS_FILE


def load_synopsis() -> str:
    if not SYNOPSIS_FILE.exists():
        return ""
    return SYNOPSIS_FILE.read_text(encoding="utf-8")
