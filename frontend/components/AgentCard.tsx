"use client";

import clsx from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import { BookOpen, Coins, Edit3, Hash, Timer, Wrench, Cpu } from "lucide-react";
import { useState } from "react";
import type { AgentStatus } from "@/lib/types";
import { getAgentIcon } from "./Icons";

const STATUS_LABEL: Record<string, string> = {
  idle: "等待",
  queued: "排队",
  running: "工作中",
  awaiting_intervention: "等待人工干预",
  done: "已完成",
  error: "异常",
  skipped: "跳过",
};

const STATUS_TONE: Record<string, string> = {
  idle: "text-slate-400 border-slate-500/30 bg-slate-500/10",
  queued: "text-slate-300 border-slate-400/30 bg-slate-500/10",
  running:
    "text-cyan-200 border-cyan-300/40 bg-cyan-400/10 shadow-[0_0_24px_-6px_rgba(34,211,238,0.6)]",
  awaiting_intervention:
    "text-amber-200 border-amber-300/40 bg-amber-400/10 shadow-[0_0_24px_-6px_rgba(251,191,36,0.55)]",
  done: "text-emerald-200 border-emerald-300/40 bg-emerald-400/10",
  error: "text-rose-200 border-rose-300/40 bg-rose-400/10",
  skipped: "text-slate-400 border-slate-500/30 bg-slate-500/10",
};

export interface AgentCardProps {
  agent: AgentStatus;
  index: number;
  onIntervene?: (agent: AgentStatus) => void;
  isInterveneAvailable?: boolean;
}

export function AgentCard({
  agent,
  index,
  onIntervene,
  isInterveneAvailable,
}: AgentCardProps) {
  const Icon = getAgentIcon(agent.icon);
  const [expand, setExpand] = useState(false);
  const isActive =
    agent.status === "running" || agent.status === "awaiting_intervention";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, type: "spring", stiffness: 220, damping: 22 }}
      className="panel-glow relative p-4 group"
      style={{
        boxShadow: isActive
          ? `0 0 0 1px ${agent.color}55, 0 12px 36px -12px ${agent.color}90`
          : undefined,
      }}
    >
      {/* glow halo */}
      {isActive && (
        <motion.div
          className="absolute -inset-px rounded-2xl pointer-events-none"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          style={{
            background: `radial-gradient(circle at 50% 0%, ${agent.color}30, transparent 60%)`,
          }}
        />
      )}

      <div className="relative flex items-start gap-3">
        <div
          className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10"
          style={{
            background: `linear-gradient(135deg, ${agent.color}33, transparent)`,
          }}
        >
          <Icon size={20} style={{ color: agent.color }} />
          {isActive && (
            <span
              className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full animate-pulse-soft"
              style={{ background: agent.color }}
            />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-wide text-slate-100 truncate">
                {agent.name}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                {agent.role}
              </div>
            </div>
            <span
              className={clsx(
                "badge whitespace-nowrap",
                STATUS_TONE[agent.status] || STATUS_TONE.idle
              )}
            >
              <span
                className={clsx(
                  "h-1.5 w-1.5 rounded-full",
                  agent.status === "running" && "animate-pulse"
                )}
                style={{
                  background:
                    agent.status === "running" ? agent.color : "currentColor",
                }}
              />
              {STATUS_LABEL[agent.status] || agent.status}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
            <span className="inline-flex items-center gap-1">
              <Cpu size={10} />
              {agent.model}
            </span>
            {agent.uses_references && (
              <span className="inline-flex items-center gap-1 text-cyan-300/80">
                <BookOpen size={10} />
                可调用爆款范文
              </span>
            )}
          </div>
        </div>
      </div>

      {/* progress bar */}
      <div className="relative mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            background: `linear-gradient(90deg, ${agent.color}, ${agent.color}80)`,
          }}
          animate={{ width: `${Math.round(agent.progress * 100)}%` }}
          transition={{ type: "spring", stiffness: 140, damping: 20 }}
        />
        {isActive && (
          <div className="absolute inset-0 shimmer-line opacity-50 mix-blend-screen" />
        )}
      </div>

      {/* stats grid */}
      <div className="mt-3 grid grid-cols-4 gap-2 text-[10px]">
        <Stat
          icon={<Coins size={11} />}
          label="Token"
          value={agent.total_tokens.toLocaleString()}
          accent={agent.color}
        />
        <Stat
          icon={<Hash size={11} />}
          label="LLM 调用"
          value={String(agent.llm_calls)}
        />
        <Stat
          icon={<Wrench size={11} />}
          label="工具调用"
          value={String(agent.tool_calls)}
        />
        <Stat
          icon={<Timer size={11} />}
          label="耗时"
          value={fmtMs(agent.latency_ms)}
        />
      </div>

      {/* live message */}
      <div className="mt-3 min-h-[36px] rounded-lg border border-white/5 bg-black/30 p-2 font-mono text-[11px] leading-relaxed text-slate-300/90">
        <AnimatePresence mode="popLayout">
          <motion.div
            key={agent.last_message || "empty"}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
            className="line-clamp-2"
          >
            {agent.last_message || (
              <span className="text-slate-600">— 等待启动 —</span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <button
          onClick={() => setExpand((v) => !v)}
          className="text-[11px] text-slate-400 hover:text-slate-200 transition"
        >
          {expand ? "收起" : "查看产出"}
        </button>
        <button
          disabled={!isInterveneAvailable}
          onClick={() => onIntervene?.(agent)}
          className={clsx(
            "btn !py-1.5 !px-2.5 !text-[11px]",
            isInterveneAvailable
              ? "bg-amber-400/15 border border-amber-300/40 text-amber-100 hover:bg-amber-400/25"
              : "bg-white/[0.03] border border-white/10 text-slate-500"
          )}
        >
          <Edit3 size={12} />
          人工干预
        </button>
      </div>

      <AnimatePresence initial={false}>
        {expand && agent.output_preview && (
          <motion.pre
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 max-h-44 overflow-auto rounded-lg border border-white/5 bg-black/40 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-slate-300 scrollbar-thin"
          >
            {agent.output_preview}
          </motion.pre>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function Stat({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 px-2 py-1.5">
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-wide text-slate-500">
        {icon} {label}
      </div>
      <div
        className="mt-0.5 font-mono text-xs tabular-nums text-slate-100"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </div>
  );
}

function fmtMs(ms: number) {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m${Math.round(s % 60)}s`;
}
