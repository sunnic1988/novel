"""记忆管理 — 基于ChromaDB的向量化存储，用于爆款范文参考和上下文检索"""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

from novel_agents.book.paths import get_active_script, references_dir

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DIR = PROJECT_ROOT / ".chroma_db"


def _get_client() -> chromadb.ClientAPI:
    return chromadb.Client(
        Settings(
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=str(CHROMA_DIR),
        )
    )


def get_reference_collection() -> chromadb.Collection:
    """爆款范文参考集合"""
    client = _get_client()
    sid = get_active_script()
    name = f"reference_texts__{sid}"
    return client.get_or_create_collection(
        name=name,
        metadata={"description": "修仙小说爆款范文片段"},
    )


def get_chapters_collection() -> chromadb.Collection:
    """已写章节集合 — 用于上下文连贯性检索"""
    client = _get_client()
    sid = get_active_script()
    name = f"written_chapters__{sid}"
    return client.get_or_create_collection(
        name=name,
        metadata={"description": "已完成的章节内容"},
    )


def ingest_reference_texts() -> int:
    """将 references/ 目录下的 .md/.txt 文件切分并向量化入库"""
    collection = get_reference_collection()
    ref_dir = references_dir()
    if not ref_dir.exists():
        return 0

    ingested = 0
    for fpath in sorted(ref_dir.glob("*.md")) + sorted(ref_dir.glob("*.txt")):
        content = fpath.read_text(encoding="utf-8").strip()
        if not content:
            continue

        chunks = _split_text(content, chunk_size=500, overlap=80)
        ids = [f"{fpath.stem}__chunk_{i}" for i in range(len(chunks))]

        existing = set(collection.get(ids=ids)["ids"])
        new_ids, new_docs, new_metas = [], [], []
        for cid, chunk in zip(ids, chunks):
            if cid not in existing:
                new_ids.append(cid)
                new_docs.append(chunk)
                new_metas.append({"source": fpath.name, "type": "reference"})

        if new_ids:
            collection.add(ids=new_ids, documents=new_docs, metadatas=new_metas)
            ingested += len(new_ids)

    return ingested


def ingest_chapter(chapter_num: int, content: str) -> None:
    """将已完成章节向量化入库"""
    collection = get_chapters_collection()
    chunks = _split_text(content, chunk_size=500, overlap=80)
    ids = [f"ch{chapter_num:03d}__chunk_{i}" for i in range(len(chunks))]
    metas = [{"chapter": chapter_num, "type": "chapter"} for _ in chunks]
    collection.upsert(ids=ids, documents=chunks, metadatas=metas)


def query_references(query: str, n_results: int = 5) -> list[str]:
    """从爆款范文库中检索相关片段"""
    collection = get_reference_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
    return results["documents"][0] if results["documents"] else []


def query_chapters(query: str, n_results: int = 3) -> list[str]:
    """从已写章节中检索相关上下文"""
    collection = get_chapters_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
    return results["documents"][0] if results["documents"] else []


def _split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """按字符数切分文本，保留重叠"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks if chunks else [text]
