"""读者评论 / 反馈 — 反向输入到下一章规划

文件：feedback/chXXX-comments.md
"""

from __future__ import annotations

from novel_agents.book.paths import FEEDBACK_DIR, feedback_path


def save(chapter: int, text: str) -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    feedback_path(chapter).write_text(text.strip() + "\n", encoding="utf-8")


def load(chapter: int) -> str:
    p = feedback_path(chapter)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def list_all() -> list[dict]:
    if not FEEDBACK_DIR.exists():
        return []
    out = []
    for f in sorted(FEEDBACK_DIR.glob("ch*-comments.md")):
        stem = f.stem  # ch001-comments
        try:
            chnum = int(stem.split("-")[0].replace("ch", ""))
        except ValueError:
            continue
        out.append({"chapter": chnum, "text": f.read_text(encoding="utf-8")})
    return out


def latest_for_planning(up_to: int, max_chapters: int = 3) -> str:
    """汇总前 max_chapters 章的读者反馈，供下一章规划参考"""
    parts = []
    for n in range(max(1, up_to - max_chapters), up_to):
        t = load(n)
        if t:
            parts.append(f"### 第{n}章读者反馈\n{t}")
    return "\n\n".join(parts)
