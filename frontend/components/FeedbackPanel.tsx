"use client";

import { Check, MessageSquare, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function FeedbackPanel({
  chapter,
  refreshKey = 0,
}: {
  chapter: number | null;
  refreshKey?: number;
}) {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);
  const [feedbacks, setFeedbacks] = useState<
    Array<{ chapter: number; text: string }>
  >([]);

  useEffect(() => {
    api
      .listFeedback()
      .then((r) => {
        setFeedbacks(r.items);
        if (chapter) {
          const cur = r.items.find((f) => f.chapter === chapter);
          setText(cur?.text || "");
        }
      })
      .catch(() => {});
  }, [chapter, refreshKey]);

  const handleSave = async () => {
    if (!chapter) return;
    await api.saveFeedback(chapter, text);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="panel-glow p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-amber-300" />
          <h3 className="text-sm font-semibold text-slate-100">
            读者反馈 · 反向输入
          </h3>
          <span className="badge border-amber-300/30 bg-amber-400/10 text-amber-200">
            {feedbacks.length} 章
          </span>
        </div>
        {chapter && (
          <button
            onClick={handleSave}
            disabled={saved}
            className="btn-ghost !py-1 !text-[11px]"
          >
            {saved ? <Check size={11} /> : <Save size={11} />}
            {saved ? "已保存" : "保存到第 " + chapter + " 章"}
          </button>
        )}
      </div>
      <div className="mt-1 text-[10px] text-slate-500">
        填写读者评论摘要后，下一章规划阶段会自动读取并反映到节奏调整中。
      </div>
      {chapter ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder="例：催更主线，配角苏婉清评论区呼声高，希望第 N 章给她更多戏份。"
          className="mt-2 w-full rounded-lg border border-white/10 bg-black/40 p-2 text-[12px] leading-relaxed text-slate-100 outline-none focus:border-amber-300/40 scrollbar-thin"
        />
      ) : (
        <div className="mt-2 rounded-md border border-white/5 bg-black/30 p-2 text-xs text-slate-500">
          先启动一次创作流水线，确定当前章节后再输入反馈。
        </div>
      )}

      {feedbacks.length > 0 && (
        <div className="mt-3 border-t border-white/5 pt-3">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
            历史反馈
          </div>
          <div className="max-h-32 space-y-1 overflow-auto pr-1 scrollbar-thin">
            {feedbacks.map((f) => (
              <div
                key={f.chapter}
                className="rounded-md border border-white/5 bg-black/20 px-2 py-1 text-[11px] text-slate-300"
              >
                <span className="font-mono text-slate-500">
                  第 {f.chapter} 章：
                </span>
                {f.text.slice(0, 100)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
