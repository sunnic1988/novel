"""伏笔账本（foreshadowing ledger）

文件：bible/foreshadowing.yaml

每条伏笔结构：
- id: F001
- title: 简短标题
- planted_chapter: 埋设章节
- planned_payoff_chapter: 计划回收章节
- payoff_chapter: 实际回收章节（未回收则为 null）
- status: planted / payoff_due / paid_off / dropped
- importance: high / medium / low
- description: 伏笔具体内容
- related_characters: 涉及角色
- notes: 备注
"""

from __future__ import annotations

import json
from typing import Any

import yaml

from novel_agents.book.paths import foreshadowing_file


def _empty_ledger() -> dict[str, Any]:
    return {"items": []}


def load_ledger() -> dict[str, Any]:
    fp = foreshadowing_file()
    if not fp.exists():
        return _empty_ledger()
    try:
        data = yaml.safe_load(fp.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "items" not in data:
            return _empty_ledger()
        return data
    except Exception:
        return _empty_ledger()


def save_ledger(ledger: dict[str, Any]) -> None:
    fp = foreshadowing_file()
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        yaml.safe_dump(ledger, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def next_id(ledger: dict[str, Any]) -> str:
    n = len(ledger.get("items", [])) + 1
    return f"F{n:03d}"


def upsert(item: dict[str, Any]) -> dict[str, Any]:
    ledger = load_ledger()
    items = ledger.setdefault("items", [])
    if not item.get("id"):
        item["id"] = next_id(ledger)
    for i, ex in enumerate(items):
        if ex.get("id") == item["id"]:
            items[i] = {**ex, **item}
            save_ledger(ledger)
            return items[i]
    items.append(item)
    save_ledger(ledger)
    return item


def delete(item_id: str) -> bool:
    ledger = load_ledger()
    items = ledger.get("items", [])
    new_items = [i for i in items if i.get("id") != item_id]
    if len(new_items) == len(items):
        return False
    ledger["items"] = new_items
    save_ledger(ledger)
    return True


def list_items() -> list[dict[str, Any]]:
    return list(load_ledger().get("items", []))


def overdue_items(current_chapter: int) -> list[dict[str, Any]]:
    """返回计划回收章节已过但仍未回收的伏笔（红色高亮用）"""
    out = []
    for it in list_items():
        if it.get("status") in ("paid_off", "dropped"):
            continue
        ppc = it.get("planned_payoff_chapter")
        if isinstance(ppc, int) and ppc < current_chapter:
            out.append(it)
    return out


def stats(current_chapter: int | None = None) -> dict[str, Any]:
    items = list_items()
    total = len(items)
    paid_off = sum(1 for i in items if i.get("status") == "paid_off")
    dropped = sum(1 for i in items if i.get("status") == "dropped")
    open_ = sum(1 for i in items if i.get("status") in ("planted", "payoff_due", None))
    od = overdue_items(current_chapter) if current_chapter else []
    return {
        "total": total,
        "open": open_,
        "paid_off": paid_off,
        "dropped": dropped,
        "overdue": len(od),
        "overdue_items": [i.get("id") for i in od],
        "payoff_rate": round(paid_off / total, 3) if total else 0.0,
    }


def to_markdown() -> str:
    items = list_items()
    if not items:
        return "（伏笔账本为空）"
    lines = [
        "| ID | 标题 | 埋设 | 计划回收 | 实际回收 | 状态 | 重要度 |",
        "|---|---|---|---|---|---|---|",
    ]
    for it in items:
        lines.append(
            "| {id} | {title} | {pc} | {ppc} | {pc2} | {status} | {imp} |".format(
                id=it.get("id", ""),
                title=str(it.get("title", ""))[:30],
                pc=it.get("planted_chapter", ""),
                ppc=it.get("planned_payoff_chapter", ""),
                pc2=it.get("payoff_chapter", "—"),
                status=it.get("status", ""),
                imp=it.get("importance", ""),
            )
        )
    return "\n".join(lines)


def export_json() -> str:
    return json.dumps(load_ledger(), ensure_ascii=False, indent=2)
