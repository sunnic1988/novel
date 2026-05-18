"use client";

import clsx from "clsx";
import { BookOpenText, LayoutDashboard } from "lucide-react";
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

type Tab = "pipeline" | "book";

export default function Page() {
  const [tab, setTab] = useState<Tab>("pipeline");
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [activeRun, setActiveRun] = useState<RunSummary | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [interveneAgent, setInterveneAgent] = useState<AgentStatus | null>(null);
  const [bookRefreshKey, setBookRefreshKey] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  const [config, setConfig] = useState<PipelineRequest>({
    chapter_num: 1,
    chapter_title: "少年入门",
    auto_run: true,
    mode: "mock",
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
    const r = await api.createRun(req);
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
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr_1fr]">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-wide text-slate-100">
                  9 Agent · 实时状态
                </h2>
                <span className="font-mono text-[11px] text-slate-500">
                  {activeRun ? `Run #${activeRun.run_id}` : "尚未启动"}
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
                {orderedAgents.length === 0
                  ? AGENT_ORDER.map((id, idx) => (
                      <PlaceholderCard key={id} delay={idx} id={id} />
                    ))
                  : orderedAgents.map((a, idx) => (
                      <AgentCard
                        key={a.id}
                        agent={a}
                        index={idx}
                        isInterveneAvailable={
                          a.status === "awaiting_intervention" ||
                          a.status === "done" ||
                          a.status === "running"
                        }
                        onIntervene={(ag) => setInterveneAgent(ag)}
                      />
                    ))}
              </div>
            </div>

            <div className="space-y-4">
              <TracePanel events={events} agentNameOf={agentNameOf} />
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
            <div className="space-y-4">
              <MarketingPanel
                chapter={currentChapter}
                refreshKey={bookRefreshKey}
              />
              <FeedbackPanel
                chapter={currentChapter}
                refreshKey={bookRefreshKey}
              />
              <ReferenceManager />
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

function PlaceholderCard({ id, delay }: { id: string; delay: number }) {
  const label: Record<string, string> = {
    arc_architect: "卷纲架构师",
    planner: "策划师",
    pacing_doctor: "节奏医生",
    world_builder: "世界观师",
    writer: "写手",
    reviewer: "审校师",
    polisher: "润色师",
    reader_sim: "读者模拟",
    marketing_specialist: "营销专家",
  };
  return (
    <div
      className="panel relative overflow-hidden p-4"
      style={{ animationDelay: `${delay * 0.04}s` }}
    >
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl border border-white/10 bg-white/5" />
        <div>
          <div className="text-sm font-semibold text-slate-200">
            {label[id] || id}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
            待机
          </div>
        </div>
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div className="h-full w-0 bg-cyan-400/60" />
      </div>
      <div className="mt-3 min-h-[36px] rounded-lg border border-white/5 bg-black/30 p-2 text-[11px] text-slate-600">
        — 等待启动 —
      </div>
    </div>
  );
}
