"""金句库 — 自动累积写作中的高光句，避免重复 + 用于宣传

文件：bible/highlights.md（人类可读）+ 同名 yaml 元数据
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import yaml

from novel_agents.book.paths import highlights_file


@dataclass
class Highlight:
    chapter: int
    text: str
    tag: str = ""
    score: float = 0.0  # 1-5 评分


def _yaml_path() -> str:
    return str(highlights_file()) + ".yaml"


def load_all() -> list[Highlight]:
    p = _yaml_path()
    from pathlib import Path

    pp = Path(p)
    if not pp.exists():
        return []
    try:
        data = yaml.safe_load(pp.read_text(encoding="utf-8")) or {}
        items = data.get("items", [])
        return [Highlight(**i) for i in items]
    except Exception:
        return []


def save_all(items: list[Highlight]) -> None:
    fp = highlights_file()
    fp.parent.mkdir(parents=True, exist_ok=True)
    from pathlib import Path

    Path(_yaml_path()).write_text(
        yaml.safe_dump(
            {"items": [asdict(h) for h in items]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # 同步生成人类可读 md
    lines = ["# 金句库\n"]
    for h in items:
        tag = f" [{h.tag}]" if h.tag else ""
        lines.append(f"- 第{h.chapter}章{tag}：{h.text}")
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add(chapter: int, text: str, tag: str = "", score: float = 0.0) -> Highlight:
    h = Highlight(chapter=chapter, text=text.strip(), tag=tag, score=score)
    items = load_all()
    # 去重：相同 (chapter, text) 不再重复添加
    if any(i.chapter == h.chapter and i.text == h.text for i in items):
        return h
    items.append(h)
    save_all(items)
    return h


def list_for(chapter: int) -> list[Highlight]:
    return [h for h in load_all() if h.chapter == chapter]


def stats() -> dict[str, Any]:
    items = load_all()
    by_chapter: dict[int, int] = {}
    for h in items:
        by_chapter[h.chapter] = by_chapter.get(h.chapter, 0) + 1
    return {
        "total": len(items),
        "by_chapter": by_chapter,
        "average_per_chapter": (
            round(sum(by_chapter.values()) / len(by_chapter), 2) if by_chapter else 0.0
        ),
    }
