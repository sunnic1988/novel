"use client";

import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Coins,
  Copy,
  Cpu,
  Flag,
  Hand,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
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
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [stepFilter, setStepFilter] = useState<string>("");
  const [expandedCalls, setExpandedCalls] = useState<Record<string, boolean>>({});
  const listRef = useRef<HTMLDivElement>(null);
  const autoStickRef = useRef(true);

  const availableAgents = useMemo(() => {
    const ids = new Set<string>();
    for (const e of events) {
      if (e.agent) ids.add(e.agent);
    }
    return Array.from(ids);
  }, [events]);

  const filtered = useMemo(() => {
    let base = events.filter((e) => e.type !== "agent_stream_delta");
    if (filter === "llm") base = base.filter((e) => e.type === "agent_llm_call");
    if (filter === "tool") base = base.filter((e) => e.type === "agent_tool_call");
    if (filter === "milestone") {
      base = base.filter((e) =>
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
    }
    if (agentFilter !== "all") {
      base = base.filter((e) => e.agent === agentFilter);
    }
    if (stepFilter.trim()) {
      const target = Number(stepFilter.trim());
      if (!Number.isNaN(target)) {
        base = base.filter((e) => Number(e.data?.step_index) === target);
      }
    }
    return base;
  }, [events, filter, agentFilter, stepFilter]);

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
            {filtered.length} 条
          </span>
        </div>
        <div className="flex items-center gap-1">
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
          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            className="rounded-md border border-white/10 bg-black/30 px-2 py-0.5 text-[11px] text-slate-300 outline-none"
          >
            <option value="all">全部Agent</option>
            {availableAgents.map((aid) => (
              <option key={aid} value={aid}>
                {agentNameOf(aid)}
              </option>
            ))}
          </select>
          <input
            value={stepFilter}
            onChange={(e) => setStepFilter(e.target.value)}
            placeholder="步骤#"
            className="w-16 rounded-md border border-white/10 bg-black/30 px-2 py-0.5 text-[11px] text-slate-300 placeholder:text-slate-600 outline-none"
          />
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
            const promptFull = typeof e.data?.prompt_full === "string" ? e.data.prompt_full : "";
            const responseFull = typeof e.data?.response_full === "string" ? e.data.response_full : "";
            const callId = typeof e.data?.call_id === "string" ? e.data.call_id : e.id;
            const isExpanded = !!expandedCalls[callId];
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
                <div className="flex items-center justify-between gap-2 text-[10px] text-slate-500">
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon size={11} />
                    <span className={clsx("font-mono font-semibold", meta.tone)}>
                      {meta.label}
                    </span>
                    {e.agent && (
                      <span className="rounded bg-white/5 px-1 font-mono">
                        {agentNameOf(e.agent)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {tokens && (
                      <span className="font-mono text-indigo-200/90">{tokens}</span>
                    )}
                    <span className="font-mono text-slate-600">{fmtTime(e.ts)}</span>
                  </div>
                </div>
                <div className="mt-1 text-[12px] leading-snug text-slate-200/90 break-words">
                  {e.message}
                </div>
                {(promptFull || responseFull) && (
                  <div className="mt-2 rounded-md border border-white/10 bg-black/30 p-2">
                    <div className="mb-1 flex items-center justify-between">
                      <button
                        className="text-[11px] text-cyan-300 hover:text-cyan-200"
                        onClick={() =>
                          setExpandedCalls((cur) => ({ ...cur, [callId]: !isExpanded }))
                        }
                      >
                        {isExpanded ? "收起完整输入/输出" : "展开完整输入/输出"}
                      </button>
                      <div className="flex items-center gap-2">
                        {promptFull && (
                          <button
                            className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200"
                            onClick={() => navigator.clipboard.writeText(promptFull)}
                          >
                            <Copy size={10} />
                            复制Prompt
                          </button>
                        )}
                        {responseFull && (
                          <button
                            className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200"
                            onClick={() => navigator.clipboard.writeText(responseFull)}
                          >
                            <Copy size={10} />
                            复制Response
                          </button>
                        )}
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="grid gap-2 lg:grid-cols-2">
                        <div>
                          <div className="mb-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300">
                            Prompt Full
                          </div>
                          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded border border-white/10 bg-black/40 p-2 text-[11px] leading-relaxed text-slate-200 scrollbar-thin">
                            {promptFull || "（无）"}
                          </pre>
                        </div>
                        <div>
                          <div className="mb-1 text-[10px] font-mono uppercase tracking-wider text-emerald-300">
                            Response Full
                          </div>
                          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded border border-white/10 bg-black/40 p-2 text-[11px] leading-relaxed text-slate-200 scrollbar-thin">
                            {responseFull || "（无）"}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
        {filtered.length === 0 && (
          <div className="grid h-full place-items-center text-xs text-slate-600">
            — 暂无事件，启动一次创作即可看到 9 Agent 的实时留痕 —
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
