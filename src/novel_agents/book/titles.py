"""章节标题候选 + 书籍简介管理"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_agents.book.paths import bible_dir, reviews_dir, titles_path


def save_titles(chapter: int, candidates: list[dict[str, Any]]) -> Path:
    reviews_dir().mkdir(parents=True, exist_ok=True)
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
    fp = bible_dir() / "marketing_synopsis.md"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(text, encoding="utf-8")
    return fp


def load_synopsis() -> str:
    fp = bible_dir() / "marketing_synopsis.md"
    if not fp.exists():
        return ""
    return fp.read_text(encoding="utf-8")
