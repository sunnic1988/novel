"""网文 KPI — 结构化的"追订率/AI 味/爽点强度/钩子强度"等指标

文件：reviews/chXXX-kpi.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from novel_agents.book.paths import kpi_path, reviews_dir


@dataclass
class ChapterKPI:
    chapter: int
    title: str = ""
    word_count: int = 0
    # 0~1 越高越好
    retention_score: float = 0.0  # 追订率预测
    hook_strength: float = 0.0  # 章末钩子强度
    immersion_score: float = 0.0  # 沉浸感
    character_voice_score: float = 0.0  # 配角辨识度
    pace_score: float = 0.0  # 节奏
    overall_score: float = 0.0  # 综合（reviewer 给）
    # 计数类
    excitement_peaks: int = 0  # 爽点数（小+大）
    slap_face_count: int = 0  # 打脸次数
    cliffhanger_count: int = 0  # 中途悬念
    golden_lines: int = 0  # 金句数
    # AI 味（0~1 越低越好）
    ai_taste_score: float = 0.0
    # 自由文本
    notes: str = ""
    # 元数据
    enabled_agents: list[str] = field(default_factory=list)
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save(kpi: ChapterKPI) -> Path:
    reviews_dir().mkdir(parents=True, exist_ok=True)
    p = kpi_path(kpi.chapter)
    p.write_text(json.dumps(kpi.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load(chapter: int) -> ChapterKPI | None:
    p = kpi_path(chapter)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ChapterKPI(**data)
    except Exception:
        return None


def list_all() -> list[ChapterKPI]:
    rv_dir = reviews_dir()
    if not rv_dir.exists():
        return []
    out: list[ChapterKPI] = []
    for f in sorted(rv_dir.glob("ch*-kpi.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append(ChapterKPI(**data))
        except Exception:
            continue
    return out


def trend(metric: str) -> list[dict[str, Any]]:
    """返回 [{chapter, value}] 用于 UI 折线图"""
    items = list_all()
    return [
        {"chapter": k.chapter, "value": getattr(k, metric, 0.0)}
        for k in items
        if hasattr(k, metric)
    ]


def book_summary() -> dict[str, Any]:
    items = list_all()
    if not items:
        return {
            "chapters": 0,
            "avg_retention": 0.0,
            "avg_hook": 0.0,
            "avg_ai_taste": 0.0,
            "total_golden_lines": 0,
            "total_words": 0,
        }
    n = len(items)
    return {
        "chapters": n,
        "avg_retention": round(sum(i.retention_score for i in items) / n, 3),
        "avg_hook": round(sum(i.hook_strength for i in items) / n, 3),
        "avg_pace": round(sum(i.pace_score for i in items) / n, 3),
        "avg_immersion": round(sum(i.immersion_score for i in items) / n, 3),
        "avg_ai_taste": round(sum(i.ai_taste_score for i in items) / n, 3),
        "total_golden_lines": sum(i.golden_lines for i in items),
        "total_excitement_peaks": sum(i.excitement_peaks for i in items),
        "total_words": sum(i.word_count for i in items),
    }
