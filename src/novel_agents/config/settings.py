"""项目配置"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

BIBLE_DIR = PROJECT_ROOT / "bible"
CHAPTERS_DIR = PROJECT_ROOT / "chapters"
PLANS_DIR = PROJECT_ROOT / "plans"
REVIEWS_DIR = PROJECT_ROOT / "reviews"
REFERENCES_DIR = PROJECT_ROOT / "references"
FACTS_DIR = PROJECT_ROOT / "facts"
OUTPUT_DIR = PROJECT_ROOT / "output"

CHAPTER_WORD_COUNT_MIN = 2000
CHAPTER_WORD_COUNT_MAX = 3000

REVIEW_PASS_THRESHOLD = 40
MAX_REVIEW_ROUNDS = 3
