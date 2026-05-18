"""角色 runtime — 动态追踪角色当前境界 / 心境 / 关系 / 心结

文件：bible/characters/<name>.runtime.yaml
每章末由 world_builder 更新一次。
"""

from __future__ import annotations

from typing import Any

import yaml

from novel_agents.book.paths import character_runtime_path, characters_dir


def load_runtime(name: str) -> dict[str, Any]:
    p = character_runtime_path(name)
    if not p.exists():
        return {"name": name, "snapshots": []}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {
            "name": name,
            "snapshots": [],
        }
    except Exception:
        return {"name": name, "snapshots": []}


def save_runtime(data: dict[str, Any]) -> None:
    name = data.get("name") or "未命名"
    p = character_runtime_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def append_snapshot(name: str, chapter: int, snapshot: dict[str, Any]) -> dict[str, Any]:
    """新增一次 runtime 快照，snapshot 可包含：
    realm/境界, mood/心境, key_relations, knot/心结, status, notes
    """
    data = load_runtime(name)
    snaps = data.setdefault("snapshots", [])
    snap = {"chapter": chapter, **snapshot}
    snaps.append(snap)
    # 保持最近 50 条快照
    if len(snaps) > 50:
        data["snapshots"] = snaps[-50:]
    save_runtime(data)
    return data


def list_all() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    chars_dir = characters_dir()
    if not chars_dir.exists():
        return out
    for f in sorted(chars_dir.glob("*.runtime.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            out.append(data)
        except Exception:
            continue
    return out


def latest_state(name: str) -> dict[str, Any] | None:
    data = load_runtime(name)
    snaps = data.get("snapshots") or []
    if not snaps:
        return None
    return snaps[-1]
