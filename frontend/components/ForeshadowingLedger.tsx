"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import { AlertTriangle, Plus, Target, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ForeshadowingItem } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  planted: "已埋设",
  payoff_due: "待回收",
  paid_off: "已回收",
  dropped: "已放弃",
};

const STATUS_TONE: Record<string, string> = {
  planted: "border-cyan-300/30 bg-cyan-400/10 text-cyan-200",
  payoff_due: "border-amber-300/30 bg-amber-400/10 text-amber-200",
  paid_off: "border-emerald-300/30 bg-emerald-400/10 text-emerald-200",
  dropped: "border-slate-500/30 bg-white/5 text-slate-300",
};

const IMP_TONE: Record<string, string> = {
  high: "border-rose-300/40 bg-rose-400/10 text-rose-200",
  medium: "border-amber-300/30 bg-amber-400/10 text-amber-200",
  low: "border-slate-500/30 bg-white/5 text-slate-400",
};

export function ForeshadowingLedger({
  currentChapter,
  refreshKey = 0,
}: {
  currentChapter?: number;
  refreshKey?: number;
}) {
  const [items, setItems] = useState<ForeshadowingItem[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState<Partial<ForeshadowingItem>>({
    title: "",
    planted_chapter: currentChapter || 1,
    planned_payoff_chapter: (currentChapter || 1) + 10,
    importance: "medium",
    status: "planted",
  });

  const refresh = () =>
    api
      .listForeshadowing(currentChapter)
      .then((r) => {
        setItems(r.items);
        setStats(r.stats);
      })
      .catch(() => {});

  useEffect(() => {
    refresh();
  }, [currentChapter, refreshKey]);

  const handleAdd = async () => {
    if (!draft.title) return;
    await api.upsertForeshadowing(draft as ForeshadowingItem);
    setDraft({
      title: "",
      planted_chapter: currentChapter || 1,
      planned_payoff_chapter: (currentChapter || 1) + 10,
      importance: "medium",
      status: "planted",
    });
    setShowAdd(false);
    refresh();
  };

  const handleDelete = async (id?: string) => {
    if (!id) return;
    if (!confirm(`删除伏笔 ${id}？`)) return;
    await api.deleteForeshadowing(id);
    refresh();
  };

  const handleMarkPaid = async (it: ForeshadowingItem) => {
    await api.upsertForeshadowing({
      ...it,
      status: "paid_off",
      payoff_chapter: currentChapter || it.planted_chapter,
    });
    refresh();
  };

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target size={14} className="text-cyan-300" />
          <h3 className="text-sm font-semibold text-slate-100">伏笔账本</h3>
          {stats && (
            <>
              <span className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200">
                {stats.total} 条
              </span>
              <span className="badge border-amber-300/30 bg-amber-400/10 text-amber-200">
                未回收 {stats.open}
              </span>
              {stats.overdue > 0 && (
                <motion.span
                  animate={{ opacity: [0.7, 1, 0.7] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                  className="badge border-rose-300/40 bg-rose-500/15 text-rose-200"
                >
                  <AlertTriangle size={10} /> 逾期 {stats.overdue}
                </motion.span>
              )}
              <span className="badge border-emerald-300/30 bg-emerald-400/10 text-emerald-200">
                回收率 {Math.round((stats.payoff_rate || 0) * 100)}%
              </span>
            </>
          )}
        </div>
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="btn-ghost !py-1.5 !text-[11px]"
        >
          <Plus size={12} />
          {showAdd ? "取消" : "新埋伏笔"}
        </button>
      </div>

      {showAdd && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mt-3 rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-3"
        >
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <input
              placeholder="伏笔标题"
              value={draft.title || ""}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              className="col-span-2 rounded-md bg-black/40 border border-white/10 px-2 py-1 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
            />
            <input
              type="number"
              placeholder="埋于章"
              value={draft.planted_chapter || ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  planted_chapter: parseInt(e.target.value || "0"),
                })
              }
              className="rounded-md bg-black/40 border border-white/10 px-2 py-1 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
            />
            <input
              type="number"
              placeholder="计划回收章"
              value={draft.planned_payoff_chapter || ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  planned_payoff_chapter: parseInt(e.target.value || "0"),
                })
              }
              className="rounded-md bg-black/40 border border-white/10 px-2 py-1 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
            />
            <select
              value={draft.importance}
              onChange={(e) =>
                setDraft({ ...draft, importance: e.target.value as any })
              }
              className="rounded-md bg-black/40 border border-white/10 px-2 py-1 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
            >
              <option value="high" className="bg-ink-900">
                重要：高
              </option>
              <option value="medium" className="bg-ink-900">
                重要：中
              </option>
              <option value="low" className="bg-ink-900">
                重要：低
              </option>
            </select>
            <input
              placeholder="描述"
              value={draft.description || ""}
              onChange={(e) =>
                setDraft({ ...draft, description: e.target.value })
              }
              className="col-span-3 rounded-md bg-black/40 border border-white/10 px-2 py-1 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
            />
            <button onClick={handleAdd} className="btn-primary !py-1.5 !text-[12px]">
              保存
            </button>
          </div>
        </motion.div>
      )}

      <div className="mt-3 max-h-[500px] space-y-1.5 overflow-auto pr-1 scrollbar-thin">
        {items.length === 0 && (
          <div className="grid place-items-center py-8 text-xs text-slate-500">
            — 伏笔账本为空 —
          </div>
        )}
        {items.map((it) => {
          const overdue =
            currentChapter !== undefined &&
            it.planned_payoff_chapter !== null &&
            it.planned_payoff_chapter !== undefined &&
            (it.status === "planted" || it.status === "payoff_due") &&
            it.planned_payoff_chapter < currentChapter;
          return (
            <motion.div
              layout
              key={it.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={clsx(
                "rounded-lg border bg-black/30 p-2.5",
                overdue
                  ? "border-rose-300/40 shadow-[0_0_24px_-6px_rgba(244,63,94,0.6)]"
                  : "border-white/5"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-500">
                      {it.id}
                    </span>
                    <span className="truncate text-sm font-medium text-slate-100">
                      {it.title}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    <span
                      className={clsx(
                        "badge",
                        STATUS_TONE[it.status] || STATUS_TONE.planted
                      )}
                    >
                      {STATUS_LABEL[it.status] || it.status}
                    </span>
                    <span
                      className={clsx(
                        "badge",
                        IMP_TONE[it.importance] || IMP_TONE.medium
                      )}
                    >
                      {it.importance === "high"
                        ? "高重要"
                        : it.importance === "low"
                          ? "低重要"
                          : "中重要"}
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">
                      埋于 {it.planted_chapter} 章
                    </span>
                    {it.planned_payoff_chapter != null && (
                      <span className="font-mono text-[10px] text-slate-500">
                        计划回收 {it.planned_payoff_chapter} 章
                      </span>
                    )}
                    {it.payoff_chapter != null && (
                      <span className="font-mono text-[10px] text-emerald-300">
                        实际 {it.payoff_chapter} 章
                      </span>
                    )}
                    {overdue && (
                      <span className="badge border-rose-300/40 bg-rose-500/15 text-rose-200">
                        <AlertTriangle size={10} /> 已逾期
                      </span>
                    )}
                  </div>
                  {it.description && (
                    <div className="mt-1 text-[11px] text-slate-400 line-clamp-2">
                      {it.description}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  {it.status !== "paid_off" && (
                    <button
                      onClick={() => handleMarkPaid(it)}
                      className="rounded-md border border-emerald-300/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-400/20"
                    >
                      标为回收
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(it.id)}
                    className="rounded-md border border-rose-300/20 bg-rose-500/5 px-2 py-0.5 text-[10px] text-rose-200 hover:bg-rose-500/15"
                  >
                    <Trash2 size={10} className="inline" />
                  </button>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
