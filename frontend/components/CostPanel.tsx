"use client";

import clsx from "clsx";
import { AlertOctagon, AlertTriangle, DollarSign, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CostEstimate } from "@/lib/types";

export function CostPanel({
  chapterNum,
  mode,
  isOpening,
  bestOfN,
  enabledAgents,
  budgetUsd,
  onBudgetChange,
  refreshKey = 0,
}: {
  chapterNum: number;
  mode: "live" | "mock";
  isOpening: boolean;
  bestOfN: number;
  enabledAgents: string[];
  budgetUsd: number | null;
  onBudgetChange: (n: number | null) => void;
  refreshKey?: number;
}) {
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [alert, setAlert] = useState<any>(null);

  useEffect(() => {
    api
      .costEstimate({
        chapter_num: chapterNum,
        mode,
        is_opening: isOpening,
        best_of_n: bestOfN,
        enabled_agents: enabledAgents,
      })
      .then(setEstimate)
      .catch(() => {});
  }, [chapterNum, mode, isOpening, bestOfN, enabledAgents.join(",")]);

  useEffect(() => {
    api.costAlerts(budgetUsd).then(setAlert).catch(() => {});
  }, [budgetUsd, refreshKey]);

  const exceeds = estimate && budgetUsd && estimate.total_cost_usd > budgetUsd;

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center gap-2">
        <Wallet size={14} className="text-amber-300" />
        <h3 className="text-sm font-semibold text-slate-100">成本预警 · 预算</h3>
      </div>

      <div className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              本章预估
            </div>
            <div className="font-mono text-2xl tabular-nums text-slate-100">
              {estimate ? `$${estimate.total_cost_usd.toFixed(3)}` : "—"}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              Token 预估
            </div>
            <div className="font-mono text-sm text-slate-300">
              {estimate?.total_tokens?.toLocaleString() || "—"}
            </div>
          </div>
        </div>
        {bestOfN > 1 && (
          <div className="mt-1 text-[10px] text-amber-300">
            Writer Best-of-{bestOfN} ⇒ 写手成本 ×{bestOfN}
          </div>
        )}
      </div>

      <div className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            <DollarSign size={11} />
            本 run 预算上限（USD，留空不限）
          </div>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <input
            type="number"
            step={0.1}
            min={0}
            placeholder="例如 0.5"
            value={budgetUsd ?? ""}
            onChange={(e) =>
              onBudgetChange(e.target.value ? Number(e.target.value) : null)
            }
            className="w-full rounded-md border border-white/10 bg-black/40 px-2 py-1 text-sm font-mono text-slate-100 outline-none focus:border-amber-300/40"
          />
          {exceeds && (
            <AlertTriangle size={14} className="text-rose-300 shrink-0" />
          )}
        </div>
        {exceeds && (
          <div className="mt-1 text-[11px] text-rose-300">
            预估 ${estimate!.total_cost_usd.toFixed(3)} 超过预算
            ${budgetUsd!.toFixed(3)}，启动时会提示。
          </div>
        )}
      </div>

      {alert && (
        <div
          className={clsx(
            "mt-3 rounded-xl border p-3 text-[11px]",
            alert.level === "exceeded"
              ? "border-rose-400/50 bg-rose-500/10 text-rose-200"
              : alert.level === "warning"
                ? "border-amber-400/40 bg-amber-500/10 text-amber-200"
                : alert.level === "info"
                  ? "border-cyan-400/30 bg-cyan-500/10 text-cyan-200"
                  : "border-emerald-400/20 bg-emerald-500/5 text-emerald-200"
          )}
        >
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase tracking-wider">
              全书累计消费
            </div>
            {alert.level === "exceeded" && (
              <AlertOctagon size={12} className="text-rose-300" />
            )}
          </div>
          <div className="mt-1 font-mono text-base">
            ${(alert.spent_usd || 0).toFixed(3)}{" "}
            {alert.budget_usd
              ? `/ $${alert.budget_usd.toFixed(3)} (${Math.round(
                  (alert.ratio || 0) * 100
                )}%)`
              : ""}
          </div>
          {alert.message && <div className="mt-1">{alert.message}</div>}
        </div>
      )}

      {estimate && estimate.breakdown && estimate.breakdown.length > 0 && (
        <div className="mt-3 border-t border-white/5 pt-3">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
            分 Agent 成本预估
          </div>
          <div className="max-h-36 space-y-1 overflow-auto pr-1 scrollbar-thin">
            {estimate.breakdown.map((b) => (
              <div
                key={b.agent}
                className="flex items-center justify-between rounded-md border border-white/5 bg-black/20 px-2 py-1 text-[11px]"
              >
                <div className="font-mono text-slate-300">{b.agent}</div>
                <div className="font-mono text-slate-500">
                  {(b.prompt_tokens + b.completion_tokens).toLocaleString()}
                </div>
                <div className="font-mono text-amber-300">
                  ${b.cost_usd.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
