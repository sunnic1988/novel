"use client";

import { FileText, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { RunArtifactItem } from "@/lib/types";

export function RunArchivePanel({ runId }: { runId: string | null }) {
  const [items, setItems] = useState<RunArtifactItem[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const sorted = useMemo(
    () => [...items].sort((a, b) => b.modified - a.modified),
    [items]
  );

  const refresh = async () => {
    if (!runId) return;
    setBusy(true);
    try {
      const res = await api.listRunArtifacts(runId);
      setItems(res.items);
      if (!selected && res.items.length > 0) {
        setSelected(res.items[0].name);
      }
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    setItems([]);
    setSelected("");
    setContent("");
    if (runId) refresh().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    if (!runId || !selected) return;
    setLoading(true);
    api
      .getRunArtifact(runId, selected)
      .then((res) => setContent(res.content))
      .catch(() => setContent("读取失败"))
      .finally(() => setLoading(false));
  }, [runId, selected]);

  if (!runId) {
    return (
      <div className="panel-glow grid min-h-[260px] place-items-center p-4 text-sm text-slate-500">
        启动一次 run 后，这里会显示完整归档文件。
      </div>
    );
  }

  return (
    <div className="grid gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-300">
            运行归档文件
          </div>
          <button
            onClick={() => refresh().catch(() => {})}
            className="text-[11px] text-slate-400 hover:text-slate-200"
          >
            <RefreshCw size={12} className={busy ? "animate-spin" : ""} />
          </button>
        </div>
        <div className="max-h-[420px] space-y-1 overflow-auto pr-1 scrollbar-thin">
          {sorted.map((it) => (
            <button
              key={it.name}
              onClick={() => setSelected(it.name)}
              className={`w-full rounded-md border px-2 py-1.5 text-left ${
                selected === it.name
                  ? "border-cyan-300/40 bg-cyan-500/10"
                  : "border-white/10 bg-black/30"
              }`}
            >
              <div className="truncate text-[12px] text-slate-200">{it.name}</div>
              <div className="text-[10px] text-slate-500">
                {fmtSize(it.size)} · {new Date(it.modified).toLocaleTimeString()}
              </div>
            </button>
          ))}
          {sorted.length === 0 && (
            <div className="text-xs text-slate-500">暂无归档文件</div>
          )}
        </div>
      </div>
      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-emerald-300">
          <FileText size={12} />
          {selected || "文件预览"}
        </div>
        <pre className="max-h-[460px] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/40 p-3 text-[12px] leading-relaxed text-slate-200 scrollbar-thin">
          {loading ? "读取中..." : content || "请选择一个文件"}
        </pre>
      </div>
    </div>
  );
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}
