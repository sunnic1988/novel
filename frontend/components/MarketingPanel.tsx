"use client";

import clsx from "clsx";
import { Check, Copy, Megaphone, Save, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TitleCandidate } from "@/lib/types";

export function MarketingPanel({
  chapter,
  scriptId,
  refreshKey = 0,
}: {
  chapter: number | null;
  scriptId: string;
  refreshKey?: number;
}) {
  const [titles, setTitles] = useState<TitleCandidate[]>([]);
  const [synopsis, setSynopsis] = useState("");
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [savedSyn, setSavedSyn] = useState(false);

  useEffect(() => {
    if (chapter) {
      api
        .getTitles(chapter, scriptId)
        .then((r) => setTitles(r.candidates))
        .catch(() => setTitles([]));
    } else {
      setTitles([]);
    }
    api.getSynopsis(scriptId).then((r) => setSynopsis(r.text)).catch(() => {});
  }, [chapter, refreshKey, scriptId]);

  const handleCopy = async (i: number, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(i);
      setTimeout(() => setCopiedIdx(null), 1200);
    } catch {}
  };

  const handleSaveSyn = async () => {
    await api.saveSynopsis(synopsis, scriptId);
    setSavedSyn(true);
    setTimeout(() => setSavedSyn(false), 1500);
  };

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center gap-2">
        <Megaphone size={14} className="text-pink-300" />
        <h3 className="text-sm font-semibold text-slate-100">营销 · 标题党 / 简介</h3>
        {chapter ? (
          <span className="badge border-pink-300/30 bg-pink-400/10 text-pink-200">
            第 {chapter} 章
          </span>
        ) : (
          <span className="badge border-slate-500/30 bg-white/5 text-slate-400">
            选择章节后显示
          </span>
        )}
      </div>

      <div className="mt-3">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <Sparkles size={11} className="text-pink-300" /> 章节标题候选（点击复制）
        </div>
        <div className="mt-2 space-y-1.5">
          {titles.length === 0 ? (
            <div className="rounded-lg border border-white/5 bg-black/30 p-2 text-xs text-slate-500">
              本章尚未生成标题候选。运行一次创作流水线，营销专家会自动产出 5 个候选。
            </div>
          ) : (
            titles.map((t, i) => (
              <button
                key={i}
                onClick={() => handleCopy(i, t.title)}
                className={clsx(
                  "group w-full rounded-lg border bg-black/30 px-2.5 py-2 text-left transition",
                  copiedIdx === i
                    ? "border-emerald-300/40 bg-emerald-400/10"
                    : "border-white/5 hover:border-pink-300/30 hover:bg-pink-400/5"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-slate-100 line-clamp-2">
                      {t.title}
                    </div>
                    {t.angle && (
                      <div className="mt-0.5 text-[10px] text-slate-500">
                        切角：{t.angle}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {t.score !== undefined && (
                      <span className="font-mono text-[11px] text-pink-300">
                        {t.score.toFixed(1)}
                      </span>
                    )}
                    {copiedIdx === i ? (
                      <Check size={12} className="text-emerald-300" />
                    ) : (
                      <Copy
                        size={12}
                        className="text-slate-500 group-hover:text-pink-200"
                      />
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-white/5 pt-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <Wand2 size={11} className="text-pink-300" /> 书籍简介
          </div>
          <button
            onClick={handleSaveSyn}
            disabled={savedSyn}
            className={clsx(
              "btn-ghost !py-1 !text-[11px]",
              savedSyn && "!text-emerald-200 !border-emerald-300/40"
            )}
          >
            {savedSyn ? <Check size={11} /> : <Save size={11} />}
            {savedSyn ? "已保存" : "保存"}
          </button>
        </div>
        <textarea
          value={synopsis}
          onChange={(e) => setSynopsis(e.target.value)}
          rows={6}
          className="mt-2 w-full rounded-lg border border-white/10 bg-black/40 p-2 text-[12px] leading-relaxed text-slate-100 outline-none focus:border-pink-300/40 scrollbar-thin"
          placeholder="书籍简介将由营销专家自动迭代为多个候选。你也可以在这里手工编辑。"
        />
      </div>
    </div>
  );
}
