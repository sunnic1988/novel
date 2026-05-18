"use client";

import { BookMarked, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { ScriptItem } from "@/lib/types";

export function ScriptManager({
  scripts,
  currentScriptId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
}: {
  scripts: ScriptItem[];
  currentScriptId: string | null;
  onSelect: (scriptId: string) => void;
  onCreate: (name: string, description: string) => Promise<void>;
  onUpdate: (scriptId: string, patch: { name?: string; description?: string }) => Promise<void>;
  onDelete: (scriptId: string) => Promise<void>;
}) {
  const current = useMemo(
    () => scripts.find((s) => s.id === currentScriptId) ?? null,
    [scripts, currentScriptId]
  );
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const resetForm = () => {
    setName("");
    setDesc("");
  };

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BookMarked size={14} className="text-cyan-300" />
          <div className="text-sm font-semibold text-slate-100">剧本管理</div>
        </div>
        <div className="text-[11px] text-slate-500">{scripts.length} 个剧本</div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <select
          value={currentScriptId ?? ""}
          onChange={(e) => onSelect(e.target.value)}
          className="rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[12px] text-slate-100 outline-none"
        >
          {scripts.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button
          className="btn-ghost !py-1 !text-[11px]"
          onClick={() => {
            setEditing(true);
            setName(current?.name ?? "");
            setDesc(current?.description ?? "");
          }}
          disabled={!current}
        >
          <Pencil size={11} />
          编辑
        </button>
        <button
          className="btn-danger !py-1 !text-[11px]"
          onClick={async () => {
            if (!current || current.id === "default") return;
            if (!confirm(`确认删除剧本「${current.name}」？`)) return;
            setBusy(true);
            setError("");
            try {
              await onDelete(current.id);
            } catch (e: any) {
              setError(e?.message || "删除失败");
            } finally {
              setBusy(false);
            }
          }}
          disabled={!current || current.id === "default" || busy}
        >
          <Trash2 size={11} />
          删除
        </button>
      </div>

      {editing && (
        <div className="mt-3 space-y-2 rounded-lg border border-white/10 bg-black/30 p-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="剧本名称"
            className="w-full rounded-md border border-white/10 bg-black/40 px-2 py-1 text-[12px] text-slate-100 outline-none"
          />
          <textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="剧本简介（可选）"
            rows={2}
            className="w-full rounded-md border border-white/10 bg-black/40 px-2 py-1 text-[12px] text-slate-100 outline-none"
          />
          <div className="flex items-center gap-2">
            <button
              className="btn-primary !py-1 !text-[11px]"
              disabled={busy || !name.trim()}
              onClick={async () => {
                if (!current) return;
                setBusy(true);
                setError("");
                try {
                  await onUpdate(current.id, { name: name.trim(), description: desc.trim() });
                  setEditing(false);
                } catch (e: any) {
                  setError(e?.message || "保存失败");
                } finally {
                  setBusy(false);
                }
              }}
            >
              保存修改
            </button>
            <button
              className="btn-ghost !py-1 !text-[11px]"
              onClick={() => {
                setEditing(false);
                resetForm();
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      <div className="mt-3 rounded-lg border border-cyan-300/20 bg-cyan-500/5 p-3">
        <div className="mb-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300">
          新建剧本
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：凡人逆袭线"
            className="min-w-[180px] flex-1 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[12px] text-slate-100 outline-none"
          />
          <input
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="一句话描述（可选）"
            className="min-w-[220px] flex-[1.3] rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[12px] text-slate-100 outline-none"
          />
          <button
            className="btn-primary !py-1 !text-[11px]"
            disabled={busy || !name.trim()}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await onCreate(name.trim(), desc.trim());
                resetForm();
              } catch (e: any) {
                setError(e?.message || "新建失败");
              } finally {
                setBusy(false);
              }
            }}
          >
            <Plus size={11} />
            新建
          </button>
        </div>
      </div>
      {error && (
        <div className="mt-2 rounded-md border border-rose-300/30 bg-rose-500/10 px-2 py-1 text-[11px] text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}
