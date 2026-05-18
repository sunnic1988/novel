"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Send, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

function collapseDoubledTextIfNeeded(text: string): string {
  const compact = [...text].filter((ch) => !/\s/.test(ch));
  if (compact.length < 40) return text;
  const pairs = Math.floor(compact.length / 2);
  if (pairs < 20) return text;
  let samePairs = 0;
  for (let i = 0; i < pairs; i += 1) {
    if (compact[i * 2] === compact[i * 2 + 1]) samePairs += 1;
  }
  const ratio = samePairs / pairs;
  if (ratio < 0.72) return text;

  const chars = [...text];
  const out: string[] = [];
  for (let i = 0; i < chars.length; i += 1) {
    const cur = chars[i];
    const next = chars[i + 1];
    if (next !== undefined && cur === next && cur !== "\n" && cur !== "\r") {
      out.push(cur);
      i += 1;
      continue;
    }
    out.push(cur);
  }
  return out.join("");
}

function collapseRepeatedPhrasesIfNeeded(text: string): string {
  const compact = text.replace(/\s+/g, "");
  if (compact.length < 40) return text;
  let repeatedHits = 0;
  let checks = 0;
  for (let i = 0; i + 3 < compact.length; i += 1) {
    const a = compact.slice(i, i + 2);
    const b = compact.slice(i + 2, i + 4);
    checks += 1;
    if (a === b) repeatedHits += 1;
  }
  if (checks < 10 || repeatedHits / checks < 0.18) return text;

  const chars = [...text];
  const out: string[] = [];
  let i = 0;
  while (i < chars.length) {
    let collapsed = false;
    for (let span = 6; span >= 1; span -= 1) {
      if (i + span * 2 > chars.length) continue;
      const a = chars.slice(i, i + span).join("");
      const b = chars.slice(i + span, i + span * 2).join("");
      if (a === b) {
        out.push(a);
        i += span * 2;
        collapsed = true;
        break;
      }
    }
    if (!collapsed) {
      out.push(chars[i]);
      i += 1;
    }
  }
  return out.join("");
}

const INITIAL_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "我是你的玄幻创作顾问。先告诉我这章最想写的冲突或爽点，我会继续追问并帮你整理成可直接开跑的章节大纲。",
};

export function OutlineWizard({
  open,
  chapterNum,
  scriptId,
  onClose,
  onApplyOutline,
}: {
  open: boolean;
  chapterNum: number;
  scriptId: string;
  onClose: () => void;
  onApplyOutline: (outline: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setMessages([INITIAL_MESSAGE]);
    setDraft("");
    setError("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => {
      const el = listRef.current;
      if (!el) return;
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, open]);

  const canApply = useMemo(() => {
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    return !!lastAssistant && lastAssistant.content.includes("## 大纲");
  }, [messages]);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant")?.content || "",
    [messages]
  );

  const send = async (text: string) => {
    const input = text.trim();
    if (!input || busy) return;
    const userMsg: ChatMessage = { role: "user", content: input };
    const history = [...messages, userMsg];
    setMessages([...history, { role: "assistant", content: "" }]);
    setDraft("");
    setBusy(true);
    setError("");
    try {
      const full = await api.chatOutline({
        messages: history,
        chapter_num: chapterNum,
        script_id: scriptId,
      });
      const normalized = collapseRepeatedPhrasesIfNeeded(
        collapseDoubledTextIfNeeded(full)
      );
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") {
          last.content = normalized;
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur"
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 24 }}
            onClick={(e) => e.stopPropagation()}
            className="absolute inset-x-4 top-6 mx-auto flex h-[86vh] w-full max-w-4xl flex-col rounded-2xl border border-white/10 bg-gradient-to-b from-ink-900 to-ink-950 p-4 md:inset-x-0 md:p-6"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-cyan-300">
                  AI 引导创作
                </div>
                <h2 className="mt-1 text-xl font-semibold text-slate-50">
                  第 {chapterNum} 章偏好访谈与大纲生成
                </h2>
              </div>
              <button onClick={onClose} className="rounded-md p-1.5 text-slate-400 hover:bg-white/5">
                <X size={16} />
              </button>
            </div>

            <div
              ref={listRef}
              className="mt-4 flex-1 space-y-3 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3"
            >
              {messages.map((m, idx) => (
                <div
                  key={`${m.role}-${idx}`}
                  className={m.role === "user" ? "ml-auto max-w-[80%]" : "mr-auto max-w-[80%]"}
                >
                  <div
                    className={
                      m.role === "user"
                        ? "rounded-xl border border-cyan-300/30 bg-cyan-500/15 px-3 py-2 text-sm text-cyan-50"
                        : "rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-slate-200"
                    }
                  >
                    <pre className="whitespace-pre-wrap font-sans leading-relaxed">{m.content || "..."}</pre>
                  </div>
                </div>
              ))}
            </div>

            {error && <div className="mt-2 text-xs text-rose-300">{error}</div>}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                disabled={busy}
                onClick={() => send("请根据目前信息，直接生成大纲")}
                className="btn-ghost !py-1.5 !text-[12px]"
              >
                <Sparkles size={12} />
                直接生成大纲
              </button>
              <button
                disabled={!canApply || busy}
                onClick={() => onApplyOutline(latestAssistant)}
                className="btn-primary !py-1.5 !text-[12px]"
              >
                使用此大纲
              </button>
            </div>

            <div className="mt-2 flex gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void send(draft);
                  }
                }}
                rows={3}
                placeholder="输入你的想法（如：主角本章要破局、必须有反转和装逼打脸）"
                className="w-full resize-none rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/60"
              />
              <button
                disabled={busy || !draft.trim()}
                onClick={() => void send(draft)}
                className="btn-primary self-end"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                发送
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
