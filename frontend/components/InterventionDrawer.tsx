"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Edit3, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { AgentStatus } from "@/lib/types";

export function InterventionDrawer({
  agent,
  onClose,
  onSubmit,
}: {
  agent: AgentStatus | null;
  onClose: () => void;
  onSubmit: (edited: string, resume: boolean) => Promise<void> | void;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (agent) setDraft(agent.output_preview || "");
  }, [agent]);

  return (
    <AnimatePresence>
      {agent && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur"
          onClick={onClose}
        >
          <motion.div
            initial={{ x: 480, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 480, opacity: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-white/10 bg-gradient-to-b from-ink-900 to-ink-950 p-6"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-cyan-300">
                  Human-in-the-loop · 局部干预
                </div>
                <h2 className="mt-1 text-xl font-semibold text-slate-50">
                  编辑 {agent.name} 的产出
                </h2>
                <p className="mt-1 text-[12px] text-slate-400">
                  当前流程停在该 Agent，确认后才会进入下一个 Agent。
                </p>
              </div>
              <button onClick={onClose} className="rounded-md p-1.5 text-slate-400 hover:bg-white/5">
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 flex-1 overflow-hidden">
              <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-500">
                <Edit3 size={11} />
                你可以只确认继续，也可以先编辑结果再继续
              </div>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="h-full w-full resize-none rounded-xl border border-white/10 bg-black/40 p-3 font-mono text-[13px] leading-relaxed text-slate-100 outline-none focus:border-cyan-400/60 scrollbar-thin"
              />
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onSubmit(draft, false);
                    onClose();
                  } finally {
                    setBusy(false);
                  }
                }}
                className="btn-ghost"
              >
                <Save size={14} />
                仅保存（继续停留）
              </button>
              <button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onSubmit(draft, true);
                    onClose();
                  } finally {
                    setBusy(false);
                  }
                }}
                className="btn-primary"
              >
                <Save size={14} />
                确认并进入下一 Agent
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
