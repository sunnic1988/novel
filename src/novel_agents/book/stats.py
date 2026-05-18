"""本书数据看板 — 跨 run、跨章节聚合统计

数据源：
- chapters/ch*.md
- reviews/ch*-kpi.json
- summaries/ch*.md
- bible/foreshadowing.yaml
- bible/highlights.md.yaml
- bible/characters/*.runtime.yaml
- .traces/<run_id>.jsonl
"""

from __future__ import annotations

import json
from typing import Any

from novel_agents.book import character_runtime, foreshadowing, highlights, kpi
from novel_agents.book.cost import estimate_cost, price_for_model
from novel_agents.book.paths import CHAPTERS_DIR, TRACES_DIR


def _count_chinese(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def chapters_overview() -> list[dict[str, Any]]:
    out = []
    if not CHAPTERS_DIR.exists():
        return out
    for f in sorted(CHAPTERS_DIR.glob("ch*.md")):
        try:
            n = int(f.stem.replace("ch", ""))
        except ValueError:
            continue
        text = f.read_text(encoding="utf-8")
        out.append(
            {
                "chapter": n,
                "title": _extract_title(text),
                "word_count": _count_chinese(text),
                "file": str(f.relative_to(CHAPTERS_DIR.parent)),
            }
        )
    return out


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def runs_aggregate() -> dict[str, Any]:
    """扫描 .traces/*.jsonl，按 run 聚合 token 和成本"""
    total_runs = 0
    total_tokens = 0
    total_in = 0
    total_out = 0
    total_cost = 0.0
    by_run: list[dict[str, Any]] = []
    by_agent: dict[str, dict[str, Any]] = {}

    if not TRACES_DIR.exists():
        return {
            "total_runs": 0,
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "by_run": [],
            "by_agent": {},
        }

    for trace_file in sorted(TRACES_DIR.glob("*.jsonl")):
        run_id = trace_file.stem
        run_in = 0
        run_out = 0
        run_cost = 0.0
        run_calls = 0
        chapter_num: int | None = None
        chapter_title = ""
        first_ts: int | None = None
        last_ts: int | None = None

        with trace_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = e.get("ts")
                if isinstance(ts, int):
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                t = e.get("type")
                d = e.get("data", {}) or {}
                if t == "run_started":
                    chapter_num = d.get("chapter_num")
                    chapter_title = d.get("title", "")
                if t == "agent_llm_call":
                    p_in = int(d.get("prompt_tokens", 0) or 0)
                    p_out = int(d.get("completion_tokens", 0) or 0)
                    model = d.get("model", "default-analytical")
                    cost = estimate_cost(model, p_in, p_out)
                    run_in += p_in
                    run_out += p_out
                    run_cost += cost
                    run_calls += 1
                    a = e.get("agent") or "?"
                    agg = by_agent.setdefault(
                        a,
                        {
                            "agent": a,
                            "calls": 0,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "cost_usd": 0.0,
                        },
                    )
                    agg["calls"] += 1
                    agg["prompt_tokens"] += p_in
                    agg["completion_tokens"] += p_out
                    agg["cost_usd"] += cost

        total_runs += 1
        total_in += run_in
        total_out += run_out
        total_tokens += run_in + run_out
        total_cost += run_cost
        by_run.append(
            {
                "run_id": run_id,
                "chapter_num": chapter_num,
                "chapter_title": chapter_title,
                "prompt_tokens": run_in,
                "completion_tokens": run_out,
                "total_tokens": run_in + run_out,
                "cost_usd": round(run_cost, 4),
                "llm_calls": run_calls,
                "started_at": first_ts,
                "ended_at": last_ts,
            }
        )

    # round agent costs
    for a, agg in by_agent.items():
        agg["cost_usd"] = round(agg["cost_usd"], 4)

    by_run.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
    return {
        "total_runs": total_runs,
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_in,
        "total_completion_tokens": total_out,
        "total_cost_usd": round(total_cost, 4),
        "by_run": by_run,
        "by_agent": by_agent,
    }


def book_dashboard(current_chapter: int | None = None) -> dict[str, Any]:
    """汇总：章节 + 字数 + KPI 趋势 + 伏笔 + 金句 + 成本"""
    chapters = chapters_overview()
    n_chapters = len(chapters)
    if current_chapter is None and chapters:
        current_chapter = max(c["chapter"] for c in chapters)
    runs = runs_aggregate()
    kpi_sum = kpi.book_summary()
    fs = foreshadowing.stats(current_chapter)
    hl = highlights.stats()
    char_states = [
        {
            "name": d.get("name"),
            "latest": (d.get("snapshots") or [{}])[-1] if d.get("snapshots") else None,
        }
        for d in character_runtime.list_all()
    ]
    return {
        "chapters_written": n_chapters,
        "total_words": sum(c["word_count"] for c in chapters),
        "current_chapter": current_chapter,
        "kpi": kpi_sum,
        "foreshadowing": fs,
        "highlights": hl,
        "characters": char_states,
        "runs": {
            "total": runs["total_runs"],
            "total_tokens": runs["total_tokens"],
            "total_cost_usd": runs["total_cost_usd"],
            "by_agent": list(runs["by_agent"].values()),
        },
    }


def kpi_trends() -> dict[str, Any]:
    """汇总常用 KPI 趋势用于折线图"""
    return {
        "retention": kpi.trend("retention_score"),
        "hook": kpi.trend("hook_strength"),
        "pace": kpi.trend("pace_score"),
        "immersion": kpi.trend("immersion_score"),
        "ai_taste": kpi.trend("ai_taste_score"),
        "excitement_peaks": kpi.trend("excitement_peaks"),
        "golden_lines": kpi.trend("golden_lines"),
        "word_count": kpi.trend("word_count"),
    }


def pricing_table() -> list[dict[str, Any]]:
    """前端展示用价格表"""
    from novel_agents.book.cost import PRICING

    return [
        {"model": m, "input_per_1m_usd": p[0], "output_per_1m_usd": p[1]}
        for m, p in PRICING.items()
        if not m.startswith("default")
    ]


def cost_alerts(budget_usd: float | None) -> dict[str, Any]:
    """根据当前累计消耗与预算给出提示"""
    runs = runs_aggregate()
    spent = runs["total_cost_usd"]
    if budget_usd is None or budget_usd <= 0:
        return {"spent_usd": spent, "budget_usd": None, "level": "ok", "message": ""}
    ratio = spent / budget_usd if budget_usd else 0
    if ratio >= 1.0:
        level = "exceeded"
        msg = f"已超出预算 {(ratio - 1) * 100:.0f}%，建议暂停或调高预算。"
    elif ratio >= 0.8:
        level = "warning"
        msg = f"已消耗预算 {ratio * 100:.0f}%，临近上限。"
    elif ratio >= 0.5:
        level = "info"
        msg = f"已消耗预算 {ratio * 100:.0f}%。"
    else:
        level = "ok"
        msg = ""
    return {
        "spent_usd": spent,
        "budget_usd": budget_usd,
        "ratio": round(ratio, 3),
        "level": level,
        "message": msg,
    }


# --- 价格信息查询的便捷封装 ---
def price_lookup(model: str) -> dict[str, Any]:
    p_in, p_out = price_for_model(model)
    return {"model": model, "input_per_1m_usd": p_in, "output_per_1m_usd": p_out}
