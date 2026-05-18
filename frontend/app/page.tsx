"use client";

import clsx from "clsx";
import { BookOpenText, LayoutDashboard, Play, WandSparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentCard } from "@/components/AgentCard";
import { BackgroundFX } from "@/components/BackgroundFX";
import { BookOverview } from "@/components/BookOverview";
import { CostPanel } from "@/components/CostPanel";
import { FeedbackPanel } from "@/components/FeedbackPanel";
import { ForeshadowingLedger } from "@/components/ForeshadowingLedger";
import { HeroPanel, type PipelineRequest } from "@/components/HeroPanel";
import { InterventionDrawer } from "@/components/InterventionDrawer";
import { MarketingPanel } from "@/components/MarketingPanel";
import { ReferenceManager } from "@/components/ReferenceManager";
import { RunArchivePanel } from "@/components/RunArchivePanel";
import { TracePanel } from "@/components/TracePanel";
import { api, openEventStream } from "@/lib/api";
import type {
  AgentStatus,
  RunSummary,
  StatusInfo,
  TraceEvent,
} from "@/lib/types";

export const dynamic = "force-dynamic";

const AGENT_ORDER = [
  "arc_architect",
  "planner",
  "pacing_doctor",
  "world_builder",
  "writer",
  "reviewer",
  "polisher",
  "reader_sim",
  "marketing_specialist",
];

const AGENT_LABELS: Record<string, string> = {
  arc_architect: "卷纲",
  planner: "策划",
  pacing_doctor: "节奏",
  world_builder: "世观",
  writer: "写手",
  reviewer: "审校",
  polisher: "润色",
  reader_sim: "读模",
  marketing_specialist: "营销",
};

type Tab = "pipeline" | "book";

export default function Page() {
  const [tab, setTab] = useState<Tab>("pipeline");
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [activeRun, setActiveRun] = useState<RunSummary | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [interveneAgent, setInterveneAgent] = useState<AgentStatus | null>(null);
  const [bookRefreshKey, setBookRefreshKey] = useState(0);
  const [evidenceTab, setEvidenceTab] = useState<"logs" | "references" | "ops" | "archives">("logs");
  const wsRef = useRef<WebSocket | null>(null);

  const [config, setConfig] = useState<PipelineRequest>({
    chapter_num: 1,
    chapter_title: "少年入门",
    auto_run: false,
    mode: "live",
    is_opening: true,
    best_of_n: 1,
    enabled_agents: AGENT_ORDER,
    budget_usd: null,
  });

  useEffect(() => {
    api.status().then(setStatus).catch(() => {});
    api
      .listRuns()
      .then((r) => {
        if (r.runs.length > 0) {
          const newest = r.runs[0];
          setActiveRun(newest);
          api.getEvents(newest.run_id).then((res) => setEvents(res.events));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const ws = openEventStream({
      onSnapshot: (runs) => {
        if (runs.length > 0 && !activeRun) setActiveRun(runs[0]);
      },
      onRunUpdate: (run) => {
        setActiveRun((cur) => {
          if (!cur || cur.run_id === run.run_id) return run;
          return run.created_at >= cur.created_at ? run : cur;
        });
      },
      onEvent: (e) => {
        setEvents((cur) => {
          if (!activeRunRef.current || activeRunRef.current.run_id !== e.run_id)
            return cur;
          if (cur.some((c) => c.id === e.id)) return cur;
          const next = [...cur, e];
          // 检测到 artifact_saved / run_completed 时刷新本书数据
          if (
            e.type === "artifact_saved" ||
            e.type === "run_completed"
          ) {
            setBookRefreshKey((k) => k + 1);
          }
          return next.length > 600 ? next.slice(-600) : next;
        });
      },
    });
    wsRef.current = ws;
    return () => {
      try {
        ws.close();
      } catch {}
    };
  }, []);

  const activeRunRef = useRef<RunSummary | null>(activeRun);
  useEffect(() => {
    activeRunRef.current = activeRun;
  }, [activeRun]);

  useEffect(() => {
    if (!activeRun?.paused_at_agent) return;
    const paused = activeRun.agents.find((a) => a.id === activeRun.paused_at_agent) || null;
    if (paused) setInterveneAgent(paused);
  }, [activeRun]);

  const agentNameOf = useCallback(
    (id: string | null) => {
      if (!id || !activeRun) return id || "";
      return activeRun.agents.find((a) => a.id === id)?.name || id;
    },
    [activeRun]
  );

  const orderedAgents = useMemo<AgentStatus[]>(() => {
    if (!activeRun) return [];
    const map = new Map(activeRun.agents.map((a) => [a.id, a]));
    return AGENT_ORDER.map((id) => map.get(id as any)).filter(
      Boolean
    ) as AgentStatus[];
  }, [activeRun]);

  const handleStart = useCallback(async (req: PipelineRequest) => {
    const r = await api.createRun({
      ...req,
      step_confirm_mode: !req.auto_run,
    });
    setEvents([]);
    setActiveRun(r.run);
    activeRunRef.current = r.run;
    setTimeout(async () => {
      try {
        const evs = await api.getEvents(r.run_id);
        setEvents(evs.events);
      } catch {}
    }, 400);
  }, []);

  const handlePause = useCallback(async () => {
    if (!activeRun) return;
    await api.pauseRun(activeRun.run_id);
  }, [activeRun]);

  const handleResume = useCallback(async () => {
    if (!activeRun) return;
    await api.resumeRun(activeRun.run_id);
  }, [activeRun]);

  const handleAbort = useCallback(async () => {
    if (!activeRun) return;
    if (!confirm("确认终止当前流水线？")) return;
    await api.abortRun(activeRun.run_id);
  }, [activeRun]);

  const handleIntervene = useCallback(
    async (edited: string, resume: boolean) => {
      if (!activeRun || !interveneAgent) return;
      await api.intervene(activeRun.run_id, interveneAgent.id, edited, resume);
    },
    [activeRun, interveneAgent]
  );

  const currentChapter = activeRun?.chapter_num ?? config.chapter_num;
  const currentAgent = useMemo(() => {
    if (!activeRun) return null;
    if (activeRun.paused_at_agent) {
      return orderedAgents.find((a) => a.id === activeRun.paused_at_agent) || null;
    }
    return (
      orderedAgents.find((a) => a.status === "running") ||
      orderedAgents.find((a) => a.status === "awaiting_intervention") ||
      orderedAgents.find((a) => a.status === "idle" || a.status === "queued") ||
      orderedAgents[orderedAgents.length - 1] ||
      null
    );
  }, [activeRun, orderedAgents]);
  const currentIndex = currentAgent ? AGENT_ORDER.indexOf(currentAgent.id) : -1;
  const previousAgent = currentIndex > 0 ? orderedAgents[currentIndex - 1] : null;
  const nextAgent =
    currentIndex >= 0 && currentIndex < orderedAgents.length - 1
      ? orderedAgents[currentIndex + 1]
      : null;
  const quickContinue = useCallback(async () => {
    if (!activeRun || !currentAgent) return;
    await api.intervene(
      activeRun.run_id,
      currentAgent.id,
      currentAgent.output_preview || "",
      true
    );
  }, [activeRun, currentAgent]);

  return (
    <>
      <BackgroundFX />
      <main className="mx-auto max-w-[1600px] px-4 py-6 md:px-8">
        <HeroPanel
          status={status}
          run={activeRun}
          config={config}
          onConfigChange={setConfig}
          onStart={handleStart}
          onPause={handlePause}
          onResume={handleResume}
          onAbort={handleAbort}
        />

        <div className="mt-5 flex items-center gap-2">
          <TabButton
            active={tab === "pipeline"}
            onClick={() => setTab("pipeline")}
            icon={<LayoutDashboard size={13} />}
            label="Pipeline · 单 Run 仪表盘"
          />
          <TabButton
            active={tab === "book"}
            onClick={() => setTab("book")}
            icon={<BookOpenText size={13} />}
            label="本书数据 · 跨 Run / 伏笔 / KPI"
          />
        </div>

        {tab === "pipeline" ? (
          <div className="mt-4 space-y-4">
            <RunControlBanner run={activeRun} currentAgent={currentAgent} />
            <div className="grid items-start gap-4 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
              <PipelineStepList
                agents={orderedAgents}
                run={activeRun}
                onIntervene={(ag) => setInterveneAgent(ag)}
              />
              <div className="space-y-4">
                {currentAgent ? (
                  <>
                    <div className="rounded-xl border border-white/10 bg-black/25 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-300">
                            当前工作台
                          </div>
                          <div className="text-sm font-semibold text-slate-100">
                            第 {currentIndex + 1} 步 · {currentAgent.name}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {activeRun?.paused_at_agent === currentAgent.id && (
                            <button onClick={quickContinue} className="btn-primary !py-1.5 !text-[12px]">
                              <Play size={12} />
                              确认并下一步
                            </button>
                          )}
                          <button
                            onClick={() => setInterveneAgent(currentAgent)}
                            className="btn-ghost !py-1.5 !text-[12px]"
                          >
                            <WandSparkles size={12} />
                            编辑当前结果
                          </button>
                        </div>
                      </div>
                    </div>
                    <AgentCard
                      agent={currentAgent}
                      index={0}
                      isInterveneAvailable
                      onIntervene={(ag) => setInterveneAgent(ag)}
                    />
                    <div className="rounded-xl border border-white/10 bg-black/30 p-3">
                      <div className="mb-1 text-[10px] font-mono uppercase tracking-wider text-slate-500">
                        当前输出（实时）
                      </div>
                      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/40 p-3 text-[12px] leading-relaxed text-slate-200 scrollbar-thin">
                        {currentAgent.output_preview || "（正在等待该 Agent 产生输出）"}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="panel-glow p-6 text-sm text-slate-500">尚未启动 run。</div>
                )}
              </div>
              <div className="space-y-4">
                <ContextPanel
                  previousAgent={previousAgent}
                  currentAgent={currentAgent}
                  nextAgent={nextAgent}
                />
                <CostPanel
                  chapterNum={config.chapter_num}
                  mode={config.mode}
                  isOpening={config.is_opening}
                  bestOfN={config.best_of_n}
                  enabledAgents={config.enabled_agents}
                  budgetUsd={config.budget_usd}
                  onBudgetChange={(b) => setConfig({ ...config, budget_usd: b })}
                  refreshKey={bookRefreshKey}
                />
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/20 p-2">
              <div className="mb-2 flex items-center gap-2">
                <TabButton
                  active={evidenceTab === "logs"}
                  onClick={() => setEvidenceTab("logs")}
                  icon={<LayoutDashboard size={12} />}
                  label="证据层 · 调用日志"
                />
                <TabButton
                  active={evidenceTab === "references"}
                  onClick={() => setEvidenceTab("references")}
                  icon={<BookOpenText size={12} />}
                  label="证据层 · 范文与检索"
                />
                <TabButton
                  active={evidenceTab === "ops"}
                  onClick={() => setEvidenceTab("ops")}
                  icon={<WandSparkles size={12} />}
                  label="证据层 · 营销与反馈"
                />
                <TabButton
                  active={evidenceTab === "archives"}
                  onClick={() => setEvidenceTab("archives")}
                  icon={<BookOpenText size={12} />}
                  label="证据层 · 运行归档"
                />
              </div>
              {evidenceTab === "logs" && (
                <div className="min-h-[360px]">
                  <TracePanel events={events} agentNameOf={agentNameOf} />
                </div>
              )}
              {evidenceTab === "references" && (
                <div className="min-h-[360px]">
                  <ReferenceManager />
                </div>
              )}
              {evidenceTab === "ops" && (
                <div className="grid gap-4 lg:grid-cols-2">
                  <MarketingPanel
                    chapter={currentChapter}
                    refreshKey={bookRefreshKey}
                  />
                  <FeedbackPanel
                    chapter={currentChapter}
                    refreshKey={bookRefreshKey}
                  />
                </div>
              )}
              {evidenceTab === "archives" && (
                <RunArchivePanel runId={activeRun?.run_id ?? null} />
              )}
            </div>
          </div>
        ) : (
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <BookOverview refreshKey={bookRefreshKey} />
            <ForeshadowingLedger
              currentChapter={currentChapter}
              refreshKey={bookRefreshKey}
            />
          </div>
        )}

        <footer className="mt-10 text-center text-[11px] text-slate-600">
          Novel Agents Dashboard · 9 Agent · 15 项爆款工业流水线工具集
        </footer>
      </main>

      <InterventionDrawer
        agent={interveneAgent}
        onClose={() => setInterveneAgent(null)}
        onSubmit={handleIntervene}
      />
    </>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[12px] font-medium transition",
        active
          ? "bg-gradient-to-r from-cyan-400/20 to-indigo-400/20 text-cyan-100 border border-cyan-300/40 shadow-[0_0_24px_-8px_rgba(34,211,238,0.5)]"
          : "bg-white/[0.03] border border-white/10 text-slate-400 hover:text-slate-100"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function RunControlBanner({
  run,
  currentAgent,
}: {
  run: RunSummary | null;
  currentAgent: AgentStatus | null;
}) {
  const doneCount = run?.agents.filter((a) => a.status === "done").length ?? 0;
  return (
    <div className="rounded-xl border border-cyan-300/20 bg-cyan-500/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-slate-200">
          {run
            ? `当前运行：第 ${run.chapter_num} 章 · Run #${run.run_id}`
            : "当前运行：未启动"}
        </div>
        <div className="font-mono text-[12px] text-cyan-200">进度 {doneCount}/9</div>
      </div>
      <div className="mt-1 text-[12px] text-slate-400">
        {run?.paused_at_agent
          ? `等待你确认：${currentAgent?.name || run.paused_at_agent}`
          : currentAgent
            ? `执行中：${currentAgent.name}`
            : "启动后将进入逐 Agent 串行确认流程"}
      </div>
    </div>
  );
}

function PipelineStepList({
  agents,
  run,
  onIntervene,
}: {
  agents: AgentStatus[];
  run: RunSummary | null;
  onIntervene: (agent: AgentStatus) => void;
}) {
  if (agents.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-slate-500">
        还没有运行数据。
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-2">
      <div className="mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-500">
        流程层 · 9 步时间线
      </div>
      <div className="space-y-1.5">
        {agents.map((a, idx) => (
          <button
            key={a.id}
            onClick={() => onIntervene(a)}
            className={clsx(
              "w-full rounded-md border px-2 py-2 text-left transition",
              a.status === "done" && "border-emerald-300/30 bg-emerald-500/10",
              a.status === "running" && "border-cyan-300/30 bg-cyan-500/10",
              a.status === "awaiting_intervention" && "border-amber-300/40 bg-amber-500/15",
              a.status === "idle" && "border-white/10 bg-white/[0.02]",
              a.status === "skipped" && "border-slate-500/30 bg-white/[0.03]"
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="text-[12px] font-medium text-slate-200">
                {idx + 1}. {a.name}
              </div>
              <span className="text-[10px] text-slate-500">{statusLabel(a.status)}</span>
            </div>
            <div className="mt-0.5 line-clamp-1 text-[11px] text-slate-400">
              {a.last_message || "等待执行"}
            </div>
            {run?.paused_at_agent === a.id && (
              <div className="mt-1 text-[10px] text-amber-200">当前待确认</div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function ContextPanel({
  previousAgent,
  currentAgent,
  nextAgent,
}: {
  previousAgent: AgentStatus | null;
  currentAgent: AgentStatus | null;
  nextAgent: AgentStatus | null;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-500">
        上下文层
      </div>
      <div className="space-y-3 text-[12px]">
        <ContextBlock title="上一步产出" content={previousAgent?.output_preview || "（无）"} />
        <ContextBlock title="当前步骤" content={currentAgent?.name || "（未开始）"} />
        <ContextBlock title="下一步骤" content={nextAgent?.name || "（流程结束）"} />
      </div>
    </div>
  );
}

function ContextBlock({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-mono uppercase tracking-wider text-slate-500">
        {title}
      </div>
      <div className="rounded-md border border-white/10 bg-black/30 p-2 text-slate-300 line-clamp-3">
        {content}
      </div>
    </div>
  );
}

function statusLabel(status: AgentStatus["status"]) {
  return (
    {
      idle: "待机",
      queued: "排队",
      running: "进行中",
      awaiting_intervention: "待确认",
      done: "完成",
      error: "异常",
      skipped: "跳过",
    }[status] || status
  );
}
