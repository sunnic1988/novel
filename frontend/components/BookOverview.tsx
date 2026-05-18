"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import {
  BookOpenText,
  Coins,
  Flame,
  Quote,
  Sparkles,
  TimerReset,
  TrendingDown,
  TrendingUp,
  Users2,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BookDashboard, KpiTrends } from "@/lib/types";
import { Sparkline } from "./Sparkline";

export function BookOverview({ refreshKey = 0 }: { refreshKey?: number }) {
  const [data, setData] = useState<BookDashboard | null>(null);
  const [trends, setTrends] = useState<KpiTrends | null>(null);

  useEffect(() => {
    api.bookDashboard().then(setData).catch(() => {});
    api.kpiTrends().then(setTrends).catch(() => {});
  }, [refreshKey]);

  if (!data) {
    return (
      <div className="panel-glow grid place-items-center p-8 text-sm text-slate-500">
        正在加载本书数据…
      </div>
    );
  }

  const kpi = data.kpi || {};
  return (
    <div className="space-y-4">
      {/* 顶部 KPI 大牌 */}
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        <BigStat
          icon={<BookOpenText size={14} />}
          label="已写章节"
          value={String(data.chapters_written)}
          sub={`${data.total_words.toLocaleString()} 字`}
          color="from-cyan-400 to-sky-500"
        />
        <BigStat
          icon={<Coins size={14} />}
          label="累计 Token"
          value={data.runs.total_tokens.toLocaleString()}
          sub={`${data.runs.total} 次创作`}
          color="from-indigo-400 to-violet-500"
        />
        <BigStat
          icon={<Wallet size={14} />}
          label="累计成本 USD"
          value={`$${data.runs.total_cost_usd.toFixed(3)}`}
          sub={
            data.chapters_written
              ? `平均 $${(data.runs.total_cost_usd / Math.max(1, data.chapters_written)).toFixed(3)} / 章`
              : "—"
          }
          color="from-amber-400 to-rose-500"
        />
        <BigStat
          icon={<Flame size={14} />}
          label="伏笔回收率"
          value={`${Math.round((data.foreshadowing.payoff_rate || 0) * 100)}%`}
          sub={`未回收 ${data.foreshadowing.open} / 逾期 ${data.foreshadowing.overdue}`}
          color={
            data.foreshadowing.overdue > 0
              ? "from-rose-500 to-pink-500"
              : "from-emerald-400 to-teal-500"
          }
          warning={data.foreshadowing.overdue > 0}
        />
      </div>

      {/* KPI 趋势小图 6 联 */}
      <div className="panel-glow p-4">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp size={14} className="text-cyan-300" />
          <h3 className="text-sm font-semibold text-slate-100">网文 KPI 趋势</h3>
          <span className="badge border-cyan-300/30 bg-cyan-400/10 text-cyan-200">
            {trends?.retention?.length || 0} 章数据
          </span>
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <TrendCard
            label="追订率预测"
            value={kpi.avg_retention}
            data={trends?.retention || []}
            color="#22d3ee"
            higherBetter
          />
          <TrendCard
            label="章末钩子"
            value={kpi.avg_hook}
            data={trends?.hook || []}
            color="#3b82f6"
            higherBetter
          />
          <TrendCard
            label="节奏分"
            value={kpi.avg_pace}
            data={trends?.pace || []}
            color="#6366f1"
            higherBetter
          />
          <TrendCard
            label="沉浸感"
            value={kpi.avg_immersion}
            data={trends?.immersion || []}
            color="#a78bfa"
            higherBetter
          />
          <TrendCard
            label="AI 味（越低越好）"
            value={kpi.avg_ai_taste}
            data={trends?.ai_taste || []}
            color="#f472b6"
            higherBetter={false}
          />
          <TrendCard
            label="爽点数"
            value={kpi.total_excitement_peaks}
            data={trends?.excitement_peaks || []}
            color="#f59e0b"
            isCounter
          />
          <TrendCard
            label="金句数"
            value={kpi.total_golden_lines}
            data={trends?.golden_lines || []}
            color="#34d399"
            isCounter
          />
          <TrendCard
            label="单章字数"
            value={kpi.total_words}
            data={trends?.word_count || []}
            color="#94a3b8"
            isCounter
            yMaxOverride={3500}
          />
        </div>
      </div>

      {/* by_agent 成本 */}
      <div className="panel-glow p-4">
        <div className="mb-3 flex items-center gap-2">
          <Coins size={14} className="text-indigo-300" />
          <h3 className="text-sm font-semibold text-slate-100">
            按 Agent 累计 Token / 成本
          </h3>
        </div>
        {data.runs.by_agent.length === 0 ? (
          <div className="text-xs text-slate-500">尚无累计数据。</div>
        ) : (
          <div className="grid gap-2 md:grid-cols-3">
            {data.runs.by_agent.map((a) => (
              <div
                key={a.agent}
                className="rounded-xl border border-white/10 bg-black/30 p-3"
              >
                <div className="flex items-center justify-between">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                    {a.agent}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {a.calls} 次调用
                  </div>
                </div>
                <div className="mt-1 flex items-baseline justify-between">
                  <div className="font-mono text-xl tabular-nums text-slate-100">
                    {(a.prompt_tokens + a.completion_tokens).toLocaleString()}
                  </div>
                  <div className="font-mono text-sm text-amber-300">
                    ${a.cost_usd.toFixed(3)}
                  </div>
                </div>
                <div className="mt-1 font-mono text-[10px] text-slate-500">
                  in {a.prompt_tokens.toLocaleString()} / out{" "}
                  {a.completion_tokens.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 金句 + 角色 runtime */}
      <div className="grid gap-4 md:grid-cols-2">
        <HighlightsCard refreshKey={refreshKey} />
        <CharacterRuntimeCard refreshKey={refreshKey} />
      </div>
    </div>
  );
}

function BigStat({
  icon,
  label,
  value,
  sub,
  color,
  warning,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  color: string;
  warning?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="panel-glow relative overflow-hidden p-4"
    >
      <div
        className={clsx(
          "absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r",
          color
        )}
      />
      <div className="flex items-center gap-2 text-[11px] text-slate-400">
        {icon}
        {label}
        {warning && (
          <span className="ml-auto rounded-full bg-rose-500/20 px-1.5 py-0.5 text-[9px] text-rose-200">
            注意
          </span>
        )}
      </div>
      <div className="mt-1 font-mono text-2xl tabular-nums text-slate-100">
        {value}
      </div>
      <div className="text-[11px] text-slate-500">{sub}</div>
    </motion.div>
  );
}

function TrendCard({
  label,
  value,
  data,
  color,
  higherBetter,
  isCounter,
  yMaxOverride,
}: {
  label: string;
  value: number | undefined;
  data: Array<{ chapter: number; value: number }>;
  color: string;
  higherBetter?: boolean;
  isCounter?: boolean;
  yMaxOverride?: number;
}) {
  const trend = data.length >= 2 ? data[data.length - 1].value - data[0].value : 0;
  const up = trend > 0;
  return (
    <div className="rounded-xl border border-white/10 bg-black/30 p-3">
      <div className="flex items-center justify-between">
        <div className="text-[11px] text-slate-400">{label}</div>
        {data.length >= 2 && (
          <span
            className={clsx(
              "inline-flex items-center gap-0.5 text-[10px] font-mono",
              higherBetter !== undefined
                ? higherBetter
                  ? up
                    ? "text-emerald-300"
                    : "text-rose-300"
                  : up
                    ? "text-rose-300"
                    : "text-emerald-300"
                : "text-slate-400"
            )}
          >
            {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            {Math.abs(trend).toFixed(isCounter ? 0 : 2)}
          </span>
        )}
      </div>
      <div className="mt-1 font-mono text-lg tabular-nums text-slate-100">
        {value === undefined
          ? "—"
          : isCounter
            ? Number(value).toLocaleString()
            : value.toFixed(2)}
      </div>
      <Sparkline
        data={data}
        color={color}
        height={40}
        width={200}
        yMin={0}
        yMax={isCounter ? yMaxOverride ?? Math.max(...data.map((d) => d.value), 1) : 1}
      />
    </div>
  );
}

function HighlightsCard({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    api.listHighlights().then((r) => setItems(r.items)).catch(() => {});
  }, [refreshKey]);
  return (
    <div className="panel-glow p-4">
      <div className="mb-3 flex items-center gap-2">
        <Quote size={14} className="text-emerald-300" />
        <h3 className="text-sm font-semibold text-slate-100">金句库</h3>
        <span className="badge border-emerald-300/30 bg-emerald-400/10 text-emerald-200">
          {items.length} 句
        </span>
      </div>
      <div className="max-h-56 space-y-1.5 overflow-auto pr-1 scrollbar-thin">
        {items.length === 0 && (
          <div className="text-xs text-slate-500">— 还没有金句，写一章试试 —</div>
        )}
        {items.map((h, i) => (
          <div
            key={i}
            className="rounded-lg border border-white/5 bg-black/30 px-2.5 py-1.5"
          >
            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              <span className="font-mono">第 {h.chapter} 章</span>
              {h.tag && (
                <span className="rounded bg-emerald-400/10 px-1 text-emerald-300">
                  {h.tag}
                </span>
              )}
            </div>
            <div className="mt-0.5 text-[13px] leading-snug text-slate-100">
              「{h.text}」
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CharacterRuntimeCard({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    api
      .listCharacterRuntime()
      .then((r) => setItems(r.items))
      .catch(() => {});
  }, [refreshKey]);
  return (
    <div className="panel-glow p-4">
      <div className="mb-3 flex items-center gap-2">
        <Users2 size={14} className="text-violet-300" />
        <h3 className="text-sm font-semibold text-slate-100">角色弧光</h3>
        <span className="badge border-violet-300/30 bg-violet-400/10 text-violet-200">
          {items.length} 人
        </span>
      </div>
      <div className="max-h-56 space-y-1.5 overflow-auto pr-1 scrollbar-thin">
        {items.length === 0 && (
          <div className="text-xs text-slate-500">— 写完一章后会自动更新 —</div>
        )}
        {items.map((c, i) => {
          const latest = c.snapshots?.[c.snapshots.length - 1] || {};
          return (
            <div
              key={i}
              className="rounded-lg border border-white/5 bg-black/30 px-2.5 py-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-100">
                  {c.name}
                </div>
                {latest.realm && (
                  <span className="font-mono text-[10px] text-cyan-300">
                    {latest.realm}
                  </span>
                )}
              </div>
              {latest.mood && (
                <div className="mt-0.5 text-[11px] text-slate-300">
                  心境：{latest.mood}
                </div>
              )}
              {latest.knot && (
                <div className="text-[11px] text-slate-400">心结：{latest.knot}</div>
              )}
              {latest.chapter && (
                <div className="mt-0.5 inline-flex items-center gap-1 font-mono text-[10px] text-slate-500">
                  <TimerReset size={9} /> 截至第 {latest.chapter} 章
                  <Sparkles size={9} className="text-amber-300" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
