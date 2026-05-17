"use client";

import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, Coins, Cpu, Flag, Hand, Sparkles, Wrench, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TraceEvent } from "@/lib/types";

const TYPE_META: Record<
  string,
  { icon: LucideIcon; tone: string; label: string }
> = {
  run_started: { icon: Flag, tone: "text-cyan-300", label: "RUN START" },
  run_completed: { icon: Flag, tone: "text-emerald-300", label: "RUN DONE" },
  run_error: { icon: X, tone: "text-rose-300", label: "RUN ERROR" },
  agent_started: { icon: Sparkles, tone: "text-sky-300", label: "AGENT START" },
  agent_completed: { icon: Sparkles, tone: "text-emerald-300", label: "AGENT DONE" },
  agent_llm_call: { icon: Coins, tone: "text-indigo-300", label: "LLM" },
  agent_tool_call: { icon: Wrench, tone: "text-cyan-300", label: "TOOL" },
  agent_thinking: { icon: Cpu, tone: "text-slate-300", label: "THINK" },
  intervention_requested: { icon: Hand, tone: "text-amber-300", label: "AWAIT HUMAN" },
  intervention_applied: { icon: Hand, tone: "text-amber-200", label: "HUMAN EDIT" },
};

export function TracePanel({
  events,
  agentNameOf,
}: {
  events: TraceEvent[];
  agentNameOf: (id: string | null) => string;
}) {
  const [filter, setFilter] = useState<string>("all");
  const listRef = useRef<HTMLDivElement>(null);
  const autoStickRef = useRef(true);

  const filtered = useMemo(() => {
    if (filter === "all") return events;
    if (filter === "llm") return events.filter((e) => e.type === "agent_llm_call");
    if (filter === "tool")
      return events.filter((e) => e.type === "agent_tool_call");
    if (filter === "milestone")
      return events.filter((e) =>
        [
          "run_started",
          "run_completed",
          "agent_started",
          "agent_completed",
          "intervention_requested",
          "intervention_applied",
          "run_error",
        ].includes(e.type)
      );
    return events;
  }, [events, filter]);

  useEffect(() => {
    if (autoStickRef.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [filtered.length]);

  return (
    <div className="panel-glow flex h-full flex-col p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-cyan-300" />
          <h2 className="text-sm font-semibold tracking-wide text-slate-100">
            执行留痕
          </h2>
          <span className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200">
            {events.length} 条
          </span>
        </div>
        <div className="flex gap-1">
          {[
            { id: "all", label: "全部" },
            { id: "milestone", label: "关键" },
            { id: "llm", label: "LLM" },
            { id: "tool", label: "工具" },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={clsx(
                "rounded-md px-2 py-0.5 text-[11px] transition",
                filter === f.id
                  ? "bg-cyan-400/20 text-cyan-100 border border-cyan-300/40"
                  : "text-slate-400 hover:text-slate-200 border border-transparent"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div
        ref={listRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          autoStickRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 30;
        }}
        className="mt-3 flex-1 space-y-1.5 overflow-auto pr-1 scrollbar-thin"
      >
        <AnimatePresence initial={false}>
          {filtered.map((e) => {
            const meta = TYPE_META[e.type] || {
              icon: Activity,
              tone: "text-slate-300",
              label: e.type.toUpperCase(),
            };
            const Icon = meta.icon;
            const tokens =
              (e.data?.prompt_tokens as number | undefined) !== undefined
                ? `${e.data.prompt_tokens}↑ ${e.data.completion_tokens}↓`
                : undefined;
            return (
              <motion.div
                key={e.id}
                layout
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="rounded-lg border border-white/5 bg-black/30 px-2.5 py-1.5"
              >
                <div className="flex items-center gap-2 text-[10px] text-slate-500">
                  <Icon size={11} />
                  <span className={clsx("font-mono font-semibold", meta.tone)}>
                    {meta.label}
                  </span>
                  {e.agent && (
                    <span className="rounded bg-white/5 px-1 font-mono">
                      {agentNameOf(e.agent)}
                    </span>
                  )}
                  {tokens && (
                    <span className="ml-auto font-mono text-indigo-200/90">
                      {tokens}
                    </span>
                  )}
                  <span className="font-mono text-slate-600 ml-auto">
                    {fmtTime(e.ts)}
                  </span>
                </div>
                <div className="mt-1 text-[12px] leading-snug text-slate-200/90 break-words">
                  {e.message}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {filtered.length === 0 && (
          <div className="grid h-full place-items-center text-xs text-slate-600">
            — 暂无事件，启动一次创作即可看到 6 Agent 的实时留痕 —
          </div>
        )}
      </div>
    </div>
  );
}

function fmtTime(ts: number) {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}
