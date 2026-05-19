"""章节摘要 — 用于长上下文压缩

文件：summaries/chXXX.md
"""

from __future__ import annotations

from novel_agents.book.paths import summaries_dir, summary_path


def save(chapter: int, summary_text: str) -> None:
    summaries_dir().mkdir(parents=True, exist_ok=True)
    summary_path(chapter).write_text(summary_text.strip() + "\n", encoding="utf-8")


def load(chapter: int) -> str:
    p = summary_path(chapter)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def list_range(start: int, end: int) -> list[tuple[int, str]]:
    """返回 [start, end) 章节的摘要"""
    out: list[tuple[int, str]] = []
    for n in range(start, end):
        text = load(n)
        if text:
            out.append((n, text))
    return out


def auto_summarize(chapter_text: str, max_chars: int = 280) -> str:
    """规则法兜底摘要 — LLM 未产出摘要时使用。

    取第一段开篇 + 主要冲突段落 + 章末钩子。
    """
    text = (chapter_text or "").strip()
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return text[:max_chars]
    head = paragraphs[0][:90]
    tail = paragraphs[-1][:90]
    mid = ""
    if len(paragraphs) >= 3:
        mid_para = paragraphs[len(paragraphs) // 2]
        mid = mid_para[:90]
    parts = [head]
    if mid and mid not in head:
        parts.append(mid)
    if tail and tail not in parts:
        parts.append(tail)
    summary = "→ ".join(parts)
    return summary[:max_chars]
