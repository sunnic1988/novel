"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import {
  CircleStop,
  Cpu,
  Hash,
  KeyRound,
  Pause,
  Play,
  Rocket,
  Workflow,
} from "lucide-react";
import { Settings2 } from "lucide-react";
import { useState } from "react";
import type { RunSummary, StatusInfo } from "@/lib/types";

export interface PipelineRequest {
  script_id: string;
  chapter_num: number;
  chapter_title: string;
  synopsis_override: string;
  auto_run: boolean;
  mode: "live";
  is_opening: boolean;
  best_of_n: number;
  enabled_agents: string[];
}

const ALL_AGENTS = [
  { id: "arc_architect", name: "卷纲" },
  { id: "planner", name: "策划" },
  { id: "pacing_doctor", name: "节奏" },
  { id: "world_builder", name: "世观" },
  { id: "writer", name: "写手" },
  { id: "reviewer", name: "审校" },
  { id: "polisher", name: "润色" },
  { id: "reader_sim", name: "读模" },
  { id: "marketing_specialist", name: "营销" },
];

export function HeroPanel({
  status,
  run,
  config,
  onConfigChange,
  onStart,
  onPause,
  onResume,
  onAbort,
}: {
  status: StatusInfo | null;
  run: RunSummary | null;
  config: PipelineRequest;
  onConfigChange: (c: PipelineRequest) => void;
  onStart: (req: PipelineRequest) => void;
  onPause: () => void;
  onResume: () => void;
  onAbort: () => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const setCfg = (patch: Partial<PipelineRequest>) =>
    onConfigChange({ ...config, ...patch });

  const isRunning = run && (run.status === "running" || run.status === "paused");

  const toggleAgent = (id: string) => {
    const cur = new Set(config.enabled_agents);
    if (cur.has(id)) cur.delete(id);
    else cur.add(id);
    if (cur.size === 0) return;
    setCfg({ enabled_agents: ALL_AGENTS.map((a) => a.id).filter((x) => cur.has(x)) });
  };

  return (
    <div className="panel-glow relative p-5 md:p-6">
      <div className="relative flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Workflow size={14} className="text-cyan-300" />
            <span className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300">
              Novel Agents · Pipeline Console
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">
            <span className="grad-text">9 个 Agent</span>{" "}
            <span className="text-slate-100">协作创作一章玄幻修仙</span>
          </h1>
          <p className="mt-1 max-w-xl text-[13px] text-slate-400">
            策划 → 世界观 → 写作 → 审校 → 润色 → 读者模拟。
            每一次 LLM 调用都会完整记录提示词输入与模型输出，可逐步人工确认后继续。
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200">
              <Cpu size={11} /> Claude × DeepSeek 混合
            </span>
            <span className="badge border-indigo-300/30 bg-indigo-400/10 text-indigo-200">
              <Workflow size={11} /> CrewAI 编排
            </span>
            <span
              className={clsx(
                "badge",
                status?.has_api_key
                  ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-200"
                  : "border-amber-300/30 bg-amber-400/10 text-amber-200"
              )}
            >
              <KeyRound size={11} />
              {status?.has_api_key ? "APIMart Key 已配置" : "未配置 Key · 无法启动"}
            </span>
            <span className="badge border-slate-400/30 bg-white/5 text-slate-300">
              <Hash size={11} /> 章节 {status?.chapters_count ?? 0} 已完成
            </span>
          </div>
        </div>

        <div className="grid w-full max-w-md grid-cols-2 gap-2 md:w-auto">
          <Field label="章节号">
            <input
              type="number"
              min={1}
              value={config.chapter_num}
              onChange={(e) =>
                setCfg({ chapter_num: parseInt(e.target.value || "1") })
              }
              className="bg-transparent text-sm font-mono text-slate-100 w-full outline-none"
            />
          </Field>
          <Field label="标题">
            <input
              type="text"
              value={config.chapter_title}
              onChange={(e) => setCfg({ chapter_title: e.target.value })}
              className="bg-transparent text-sm text-slate-100 w-full outline-none"
            />
          </Field>
          <Field label="模式">
            <div className="text-sm text-slate-100">实跑 (Live)</div>
          </Field>
          <Field label="运行方式">
            <button
              onClick={() => setCfg({ auto_run: !config.auto_run })}
              className="text-left w-full text-sm text-slate-100 outline-none"
            >
              {config.auto_run ? "自动连续" : "逐 Agent 人工确认"}
            </button>
          </Field>
          <div className="col-span-2 rounded-xl border border-white/10 bg-black/30 px-3 py-2">
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              剧情想法（本次运行覆盖）
            </div>
            <textarea
              value={config.synopsis_override}
              onChange={(e) => setCfg({ synopsis_override: e.target.value })}
              rows={4}
              placeholder="在这里填你的核心剧情想法、主线冲突、角色关系、本章必出桥段..."
              className="mt-1 w-full resize-y rounded-md border border-white/10 bg-black/40 px-2 py-1 text-[12px] leading-relaxed text-slate-100 outline-none focus:border-cyan-300/40"
            />
            <div className="mt-1 text-[10px] text-slate-500">
              留空则读取当前剧本的 synopsis 文件；填写后仅覆盖本次运行。
            </div>
          </div>

          <div className="col-span-2 flex flex-wrap items-center gap-1">
            <button
              onClick={() => setCfg({ is_opening: !config.is_opening })}
              className={
                config.is_opening
                  ? "badge border-pink-300/40 bg-pink-400/15 text-pink-200"
                  : "badge border-white/10 bg-white/[0.03] text-slate-400 hover:text-pink-200"
              }
            >
              🚨 开篇 3 章模式
            </button>
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200"
            >
              <Settings2 size={10} />
              Best-of {config.best_of_n} · {config.enabled_agents.length} Agent
            </button>
          </div>

          {showAdvanced && (
            <div className="col-span-2 rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-3">
              <div className="text-[10px] uppercase tracking-wider text-cyan-300">
                Best-of-N（写手并行尝试次数）
              </div>
              <div className="mt-1 flex gap-1">
                {[1, 2, 3, 5].map((n) => (
                  <button
                    key={n}
                    onClick={() => setCfg({ best_of_n: n })}
                    className={
                      config.best_of_n === n
                        ? "rounded-md bg-cyan-400/20 text-cyan-100 border border-cyan-300/40 px-2 py-0.5 text-[11px]"
                        : "rounded-md bg-white/[0.04] border border-white/10 text-slate-300 px-2 py-0.5 text-[11px]"
                    }
                  >
                    {n}
                  </button>
                ))}
              </div>
              <div className="mt-2 text-[10px] uppercase tracking-wider text-cyan-300">
                启用 Agent
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {ALL_AGENTS.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => toggleAgent(a.id)}
                    className={
                      config.enabled_agents.includes(a.id)
                        ? "rounded-md bg-cyan-400/20 text-cyan-100 border border-cyan-300/40 px-2 py-0.5 text-[11px]"
                        : "rounded-md bg-white/[0.04] border border-white/10 text-slate-500 px-2 py-0.5 text-[11px]"
                    }
                  >
                    {a.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="col-span-2 mt-1 flex items-center gap-2">
            {!isRunning && (
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={() => onStart(config)}
                className="btn-primary flex-1"
              >
                <Rocket size={14} /> 启动 9-Agent 流水线
              </motion.button>
            )}
            {isRunning && run?.status !== "paused" && (
              <button onClick={onPause} className="btn-ghost flex-1">
                <Pause size={14} /> 暂停
              </button>
            )}
            {isRunning && run?.status === "paused" && (
              <button onClick={onResume} className="btn-primary flex-1">
                <Play size={14} /> 继续
              </button>
            )}
            {isRunning && (
              <button onClick={onAbort} className="btn-danger">
                <CircleStop size={14} /> 终止
              </button>
            )}
          </div>
        </div>
      </div>

      {run && (
        <div className="relative mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
          <MetricTile label="本次 Token" value={run.total_tokens.toLocaleString()} accent="text-cyan-300" />
          <MetricTile
            label="输入 / 输出"
            value={`${run.total_prompt_tokens.toLocaleString()} / ${run.total_completion_tokens.toLocaleString()}`}
          />
          <MetricTile label="LLM 调用次数" value={String(run.total_llm_calls)} />
          <MetricTile
            label="运行状态"
            value={STATUS_LABEL[run.status] || run.status}
            accent={STATUS_TONE[run.status]}
          />
          <MetricTile
            label="确认进度"
            value={run.paused_at_agent ? `等待 ${run.paused_at_agent}` : "9/9 串行"}
            accent="text-violet-300"
          />
        </div>
      )}
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  paused: "已暂停",
  completed: "✓ 完成",
  aborted: "已终止",
  error: "异常",
};

const STATUS_TONE: Record<string, string> = {
  running: "text-cyan-300",
  paused: "text-amber-300",
  completed: "text-emerald-300",
  aborted: "text-rose-300",
  error: "text-rose-300",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/30 px-3 py-2">
      <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
        {label}
      </div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/30 px-3 py-2">
      <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className={clsx("mt-1 font-mono text-xl tabular-nums text-slate-100", accent)}>
        {value}
      </div>
    </div>
  );
}
