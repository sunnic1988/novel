"""统一文件路径约定 — 让 6 个新数据账本都在固定位置"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ACTIVE_SCRIPT_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_script_id", default="default"
)


def _safe_script_id(script_id: str | None) -> str:
    raw = (script_id or "default").strip().lower()
    out = "".join(c for c in raw if c.isalnum() or c in "-_")
    return out or "default"


def get_active_script() -> str:
    return _safe_script_id(ACTIVE_SCRIPT_ID.get())


def set_active_script(script_id: str) -> None:
    ACTIVE_SCRIPT_ID.set(_safe_script_id(script_id))


@contextmanager
def use_script(script_id: str):
    token = ACTIVE_SCRIPT_ID.set(_safe_script_id(script_id))
    try:
        yield
    finally:
        ACTIVE_SCRIPT_ID.reset(token)


def script_root(script_id: str | None = None) -> Path:
    sid = _safe_script_id(script_id) if script_id is not None else get_active_script()
    if sid == "default":
        return PROJECT_ROOT
    return PROJECT_ROOT / "scripts" / sid


def bible_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "bible"


def arcs_dir(script_id: str | None = None) -> Path:
    return bible_dir(script_id) / "arcs"


def characters_dir(script_id: str | None = None) -> Path:
    return bible_dir(script_id) / "characters"


def foreshadowing_file(script_id: str | None = None) -> Path:
    return bible_dir(script_id) / "foreshadowing.yaml"


def highlights_file(script_id: str | None = None) -> Path:
    return bible_dir(script_id) / "highlights.md"


def chapters_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "chapters"


def reviews_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "reviews"


def summaries_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "summaries"


def feedback_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "feedback"


def plans_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "plans"


def traces_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / ".traces"


def references_dir(script_id: str | None = None) -> Path:
    return script_root(script_id) / "references"


def chapter_path(n: int) -> Path:
    return chapters_dir() / f"ch{n:03d}.md"


def summary_path(n: int) -> Path:
    return summaries_dir() / f"ch{n:03d}.md"


def kpi_path(n: int) -> Path:
    return reviews_dir() / f"ch{n:03d}-kpi.json"


def titles_path(n: int) -> Path:
    return reviews_dir() / f"ch{n:03d}-titles.json"


def ai_lint_path(n: int) -> Path:
    return reviews_dir() / f"ch{n:03d}-ai-lint.json"


def feedback_path(n: int) -> Path:
    return feedback_dir() / f"ch{n:03d}-comments.md"


def arc_path(n: int) -> Path:
    return arcs_dir() / f"arc_{n:02d}.md"


def character_runtime_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_·")
    return characters_dir() / f"{safe}.runtime.yaml"


def ensure_dirs() -> None:
    for d in (
        arcs_dir(),
        characters_dir(),
        chapters_dir(),
        reviews_dir(),
        summaries_dir(),
        feedback_dir(),
        plans_dir(),
        references_dir(),
    ):
        d.mkdir(parents=True, exist_ok=True)


def seed_script_from_default(script_id: str) -> None:
    """为新剧本生成独立基础目录，并复制默认剧本的 bible 模板。"""
    sid = _safe_script_id(script_id)
    if sid == "default":
        ensure_dirs()
        return
    dst_root = script_root(sid)
    dst_root.mkdir(parents=True, exist_ok=True)
    for d in (
        arcs_dir(sid),
        characters_dir(sid),
        chapters_dir(sid),
        reviews_dir(sid),
        summaries_dir(sid),
        feedback_dir(sid),
        plans_dir(sid),
        traces_dir(sid),
        references_dir(sid),
        bible_dir(sid) / "worldview",
    ):
        d.mkdir(parents=True, exist_ok=True)

    default_bible = bible_dir("default")
    target_bible = bible_dir(sid)
    if default_bible.exists():
        for item in default_bible.iterdir():
            target = target_bible / item.name
            if target.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, target)
