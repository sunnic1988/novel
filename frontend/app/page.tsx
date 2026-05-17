"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export const dynamic = "force-dynamic";
import { AgentCard } from "@/components/AgentCard";
import { BackgroundFX } from "@/components/BackgroundFX";
import { HeroPanel } from "@/components/HeroPanel";
import { InterventionDrawer } from "@/components/InterventionDrawer";
import { ReferenceManager } from "@/components/ReferenceManager";
import { TracePanel } from "@/components/TracePanel";
import { api, openEventStream } from "@/lib/api";
import type {
  AgentStatus,
  RunSummary,
  StatusInfo,
  TraceEvent,
} from "@/lib/types";

const AGENT_ORDER = [
  "planner",
  "world_builder",
  "writer",
  "reviewer",
  "polisher",
  "reader_sim",
];

export default function Page() {
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [activeRun, setActiveRun] = useState<RunSummary | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [interveneAgent, setInterveneAgent] = useState<AgentStatus | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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
        if (runs.length > 0 && !activeRun) {
          setActiveRun(runs[0]);
        }
      },
      onRunUpdate: (run) => {
        setActiveRun((cur) => {
          if (!cur || cur.run_id === run.run_id) return run;
          // Prefer the more recently created run
          return run.created_at >= cur.created_at ? run : cur;
        });
      },
      onEvent: (e) => {
        setEvents((cur) => {
          if (!activeRunRef.current || activeRunRef.current.run_id !== e.run_id)
            return cur;
          // 防止重复
          if (cur.some((c) => c.id === e.id)) return cur;
          const next = [...cur, e];
          return next.length > 500 ? next.slice(-500) : next;
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

  const handleStart = useCallback(async (req: any) => {
    const r = await api.createRun(req);
    setEvents([]);
    setActiveRun(r.run);
    activeRunRef.current = r.run;
    // refresh events shortly after to catch initial events
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

  const handleIntervene = useCallback(async (edited: string, resume: boolean) => {
    if (!activeRun || !interveneAgent) return;
    await api.intervene(activeRun.run_id, interveneAgent.id, edited, resume);
  }, [activeRun, interveneAgent]);

  return (
    <>
      <BackgroundFX />
      <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-8">
        <HeroPanel
          status={status}
          run={activeRun}
          onStart={handleStart}
          onPause={handlePause}
          onResume={handleResume}
          onAbort={handleAbort}
        />

        <div className="mt-6 grid gap-4 xl:grid-cols-[1.6fr_1fr_1fr]">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-wide text-slate-100">
                6 Agent · 实时状态
              </h2>
              <span className="font-mono text-[11px] text-slate-500">
                {activeRun ? `Run #${activeRun.run_id}` : "尚未启动"}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
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

          <div className="h-[680px]">
            <TracePanel events={events} agentNameOf={agentNameOf} />
          </div>
          <div className="h-[680px]">
            <ReferenceManager />
          </div>
        </div>

        <footer className="mt-10 text-center text-[11px] text-slate-600">
          Novel Agents Dashboard · Next.js 14 · CrewAI · ChromaDB · APIMart
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

function PlaceholderCard({ id, delay }: { id: string; delay: number }) {
  const label: Record<string, string> = {
    planner: "策划师",
    world_builder: "世界观师",
    writer: "写手",
    reviewer: "审校师",
    polisher: "润色师",
    reader_sim: "读者模拟",
  };
  return (
    <div
      className="panel relative overflow-hidden p-4"
      style={{ animationDelay: `${delay * 0.04}s` }}
    >
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl border border-white/10 bg-white/5" />
        <div>
          <div className="text-sm font-semibold text-slate-200">{label[id] || id}</div>
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
