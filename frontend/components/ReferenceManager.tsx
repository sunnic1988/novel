"use client";

import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  Database,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ReferenceItem } from "@/lib/types";

export function ReferenceManager({ scriptId }: { scriptId: string }) {
  const [items, setItems] = useState<ReferenceItem[]>([]);
  const [chunkCount, setChunkCount] = useState<number>(0);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [msg, setMsg] = useState<string>("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [list, status] = await Promise.all([
      api.listReferences(scriptId),
      api.status(scriptId),
    ]);
    setItems(list.items);
    setChunkCount(status.reference_chunks);
  }, [scriptId]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      setBusy(true);
      setMsg("");
      try {
        const arr = Array.from(files);
        for (const f of arr) {
          await api.uploadReference(f, scriptId);
        }
        setMsg(`已上传 ${arr.length} 个文件`);
        await refresh();
      } catch (e: any) {
        setMsg(`上传失败: ${e.message}`);
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const handleIngest = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.ingestReferences(scriptId);
      setMsg(`✓ 新增 ${r.added_chunks} 个向量片段，库内共 ${r.total_chunks} 条`);
      setChunkCount(r.total_chunks);
    } catch (e: any) {
      setMsg(`向量化失败: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`删除范文 ${name} ?`)) return;
    setBusy(true);
    try {
      await api.deleteReference(name, scriptId);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await api.searchReferences(query, 5, scriptId);
      setResults(r.results);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="panel-glow flex h-full flex-col p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-cyan-300" />
          <h2 className="text-sm font-semibold tracking-wide text-slate-100">
            爆款范文库
          </h2>
          <span className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200">
            {items.length} 文件 · {chunkCount} 向量片段
          </span>
        </div>
        <button
          onClick={handleIngest}
          disabled={busy}
          className="btn-ghost !py-1.5 !text-[11px]"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          向量化
        </button>
      </div>

      {/* Drop zone */}
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
        }}
        className={clsx(
          "mt-3 flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-5 text-center transition",
          drag
            ? "border-cyan-300/60 bg-cyan-400/10"
            : "border-white/10 bg-white/[0.02] hover:border-cyan-300/40 hover:bg-cyan-400/5"
        )}
      >
        <Upload size={18} className="text-cyan-300" />
        <div className="text-xs text-slate-200">点击或拖拽 .md / .txt 文件上传</div>
        <div className="text-[10px] text-slate-500">
          上传后点击「向量化」即可被 Agent 检索引用
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".md,.txt,text/plain,text/markdown"
          className="hidden"
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </label>

      {msg && (
        <div className="mt-2 rounded-md border border-cyan-300/20 bg-cyan-400/5 px-2 py-1 text-[11px] text-cyan-100">
          {msg}
        </div>
      )}

      <div className="mt-3 max-h-44 space-y-1.5 overflow-auto pr-1 scrollbar-thin">
        <AnimatePresence initial={false}>
          {items.map((it) => (
            <motion.div
              key={it.name}
              layout
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              className="group flex items-center justify-between gap-2 rounded-lg border border-white/5 bg-black/20 px-2.5 py-1.5"
            >
              <div className="min-w-0">
                <div className="truncate text-[12px] font-medium text-slate-100">
                  {it.name}
                </div>
                <div className="font-mono text-[10px] text-slate-500">
                  {it.char_count.toLocaleString()} 字 · {fmtSize(it.size)}
                </div>
              </div>
              <button
                onClick={() => handleDelete(it.name)}
                className="rounded-md p-1 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300 opacity-0 transition group-hover:opacity-100"
              >
                <Trash2 size={12} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
        {items.length === 0 && (
          <div className="grid place-items-center py-3 text-[11px] text-slate-600">
            — 还没有范文，上传一份开始 —
          </div>
        )}
      </div>

      <div className="mt-3 border-t border-white/5 pt-3">
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/30 px-2.5 py-1.5">
          <Search size={13} className="text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="语义检索范文片段…"
            className="flex-1 bg-transparent text-[12px] text-slate-100 placeholder:text-slate-600 outline-none"
          />
          <button
            onClick={handleSearch}
            disabled={searching || !query.trim()}
            className="text-[11px] text-cyan-200 disabled:opacity-40"
          >
            {searching ? <Loader2 size={12} className="animate-spin" /> : "搜索"}
          </button>
        </div>
        {results.length > 0 && (
          <div className="mt-2 max-h-32 space-y-1 overflow-auto pr-1 scrollbar-thin">
            {results.map((r, i) => (
              <div
                key={i}
                className="rounded-md border border-white/5 bg-black/30 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-slate-300 line-clamp-3"
              >
                {r}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function fmtSize(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}
