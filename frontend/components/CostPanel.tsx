"use client";

import { Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CostEstimate } from "@/lib/types";

export function CostPanel({
  chapterNum,
  mode,
  isOpening,
  bestOfN,
  enabledAgents,
}: {
  chapterNum: number;
  mode: "live";
  isOpening: boolean;
  bestOfN: number;
  enabledAgents: string[];
}) {
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);

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

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center gap-2">
        <Wallet size={14} className="text-amber-300" />
        <h3 className="text-sm font-semibold text-slate-100">Token 预估</h3>
      </div>

      <div className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              本章总 Token 预估
            </div>
            <div className="font-mono text-2xl tabular-nums text-slate-100">
              {estimate?.total_tokens?.toLocaleString() || "—"}
            </div>
          </div>
          <div className="text-right text-[11px] text-slate-400">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              模式
            </div>
            <div>{isOpening ? "开篇特化" : "常规章节"}</div>
          </div>
        </div>
        {bestOfN > 1 && (
          <div className="mt-1 text-[10px] text-amber-300">
            Writer Best-of-{bestOfN} ⇒ 写手 Token 消耗约 ×{bestOfN}
          </div>
        )}
      </div>

      {estimate && estimate.breakdown && estimate.breakdown.length > 0 && (
        <div className="mt-3 border-t border-white/5 pt-3">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
            分 Agent Token 预估
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
                <div className="font-mono text-slate-400">
                  in {b.prompt_tokens.toLocaleString()} / out{" "}
                  {b.completion_tokens.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
