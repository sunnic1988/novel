"""统一文件路径约定 — 让 6 个新数据账本都在固定位置"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

BIBLE_DIR = PROJECT_ROOT / "bible"
ARCS_DIR = BIBLE_DIR / "arcs"
CHARACTERS_DIR = BIBLE_DIR / "characters"
FORESHADOWING_FILE = BIBLE_DIR / "foreshadowing.yaml"
HIGHLIGHTS_FILE = BIBLE_DIR / "highlights.md"

CHAPTERS_DIR = PROJECT_ROOT / "chapters"
REVIEWS_DIR = PROJECT_ROOT / "reviews"
SUMMARIES_DIR = PROJECT_ROOT / "summaries"
FEEDBACK_DIR = PROJECT_ROOT / "feedback"
PLANS_DIR = PROJECT_ROOT / "plans"
TRACES_DIR = PROJECT_ROOT / ".traces"


def chapter_path(n: int) -> Path:
    return CHAPTERS_DIR / f"ch{n:03d}.md"


def summary_path(n: int) -> Path:
    return SUMMARIES_DIR / f"ch{n:03d}.md"


def kpi_path(n: int) -> Path:
    return REVIEWS_DIR / f"ch{n:03d}-kpi.json"


def titles_path(n: int) -> Path:
    return REVIEWS_DIR / f"ch{n:03d}-titles.json"


def ai_lint_path(n: int) -> Path:
    return REVIEWS_DIR / f"ch{n:03d}-ai-lint.json"


def feedback_path(n: int) -> Path:
    return FEEDBACK_DIR / f"ch{n:03d}-comments.md"


def arc_path(n: int) -> Path:
    return ARCS_DIR / f"arc_{n:02d}.md"


def character_runtime_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_·")
    return CHARACTERS_DIR / f"{safe}.runtime.yaml"


def ensure_dirs() -> None:
    for d in [
        ARCS_DIR,
        CHARACTERS_DIR,
        CHAPTERS_DIR,
        REVIEWS_DIR,
        SUMMARIES_DIR,
        FEEDBACK_DIR,
        PLANS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
