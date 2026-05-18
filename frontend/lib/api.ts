import type {
  CostEstimate,
  ForeshadowingItem,
  ReferenceItem,
  RunArtifactItem,
  RunSummary,
  ScriptItem,
  StatusInfo,
  TitleCandidate,
  TraceEvent,
} from "@/lib/types";

function withScript(path: string, scriptId?: string): string {
  if (!scriptId) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}script_id=${encodeURIComponent(scriptId)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = "";
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      detail = parsed?.detail || "";
    } catch {
      // ignore parse failure
    }
    throw new Error(detail || text || `${res.status} ${res.statusText}`);
  }

  return (await res.json()) as T;
}

export const api = {
  status: (scriptId?: string) => request<StatusInfo>(withScript("/api/status", scriptId)),
  listRuns: (scriptId?: string) =>
    request<{ runs: RunSummary[] }>(
      scriptId ? `/api/runs?script_id=${encodeURIComponent(scriptId)}` : "/api/runs"
    ),
  listScriptRuns: (scriptId: string) =>
    request<{ runs: RunSummary[] }>(
      `/api/scripts/${encodeURIComponent(scriptId)}/runs`
    ),
  getRun: (runId: string) => request<RunSummary>(`/api/runs/${runId}`),
  getEvents: (runId: string, limit = 5000, offset = 0) =>
    request<{ events: TraceEvent[] }>(
      `/api/runs/${runId}/events?limit=${limit}&offset=${offset}`
    ),
  listRunArtifacts: (runId: string) =>
    request<{ items: RunArtifactItem[] }>(`/api/runs/${runId}/artifacts`),
  getRunArtifact: (runId: string, name: string) =>
    request<{ name: string; size: number; content: string }>(
      `/api/runs/${runId}/artifacts/${encodeURIComponent(name)}`
    ),
  createRun: (body: object) =>
    request<{ run_id: string; run: RunSummary }>("/api/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listScripts: () => request<{ items: ScriptItem[] }>("/api/scripts"),
  createScript: (body: { id?: string; name: string; description?: string }) =>
    request<{ item: ScriptItem }>("/api/scripts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateScript: (
    scriptId: string,
    body: { name?: string; description?: string; archived?: boolean }
  ) =>
    request<{ item: ScriptItem }>(`/api/scripts/${encodeURIComponent(scriptId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteScript: (scriptId: string) =>
    request<{ ok: boolean }>(`/api/scripts/${encodeURIComponent(scriptId)}`, {
      method: "DELETE",
    }),
  pauseRun: (runId: string) =>
    request<{ ok: boolean; status: string }>(`/api/runs/${runId}/pause`, {
      method: "POST",
    }),
  resumeRun: (runId: string) =>
    request<{ ok: boolean; status: string }>(`/api/runs/${runId}/resume`, {
      method: "POST",
    }),
  abortRun: (runId: string) =>
    request<{ ok: boolean }>(`/api/runs/${runId}/abort`, { method: "POST" }),
  intervene: (
    runId: string,
    agentId: string,
    editedOutput: string,
    resume = true
  ) =>
    request<{ ok: boolean }>(`/api/runs/${runId}/agents/${agentId}/intervene`, {
      method: "POST",
      body: JSON.stringify({ edited_output: editedOutput, resume }),
    }),
  retryAgent: (runId: string, agentId: string) =>
    request<{ ok: boolean }>(`/api/runs/${runId}/agents/${agentId}/retry`, {
      method: "POST",
    }),
  chatOutline: async (
    body: {
      messages: Array<{ role: "user" | "assistant"; content: string }>;
      chapter_num: number;
      script_id: string;
    },
    onDelta?: (delta: string) => void
  ) => {
    const res = await fetch("/api/outline/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `outline chat failed: ${res.status}`);
    }
    const reader = res.body?.getReader();
    if (!reader) return "";
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const raw of chunks) {
        const line = raw
          .split("\n")
          .find((item) => item.trimStart().startsWith("data:"));
        if (!line) continue;
        const payload = line.slice(line.indexOf("data:") + 5).trim();
        if (!payload) continue;
        const parsed = JSON.parse(payload) as {
          type: "delta" | "done" | "error";
          delta?: string;
          detail?: string;
        };
        if (parsed.type === "delta" && parsed.delta) {
          full += parsed.delta;
          onDelta?.(parsed.delta);
        } else if (parsed.type === "error") {
          throw new Error(parsed.detail || "outline chat failed");
        }
      }
    }
    return full;
  },
  costEstimate: (body: object) =>
    request<CostEstimate>("/api/runs/cost-estimate", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listReferences: (scriptId?: string) =>
    request<{ items: ReferenceItem[] }>(withScript("/api/references", scriptId)),
  uploadReference: (file: File, scriptId?: string) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ ok: boolean; name: string; size: number }>(
      withScript("/api/references/upload", scriptId),
      { method: "POST", body: form }
    );
  },
  deleteReference: (name: string, scriptId?: string) =>
    request<{ ok: boolean }>(
      withScript(`/api/references/${encodeURIComponent(name)}`, scriptId),
      {
      method: "DELETE",
      }
    ),
  ingestReferences: (scriptId?: string) =>
    request<{ ok: boolean; added_chunks: number; total_chunks: number }>(
      withScript("/api/references/ingest", scriptId),
      { method: "POST" }
    ),
  searchReferences: (q: string, n = 5, scriptId?: string) =>
    request<{ results: string[] }>(
      withScript(`/api/references/search?q=${encodeURIComponent(q)}&n=${n}`, scriptId)
    ),

  bookDashboard: (scriptId?: string) =>
    request<any>(withScript("/api/book/dashboard", scriptId)),
  kpiTrends: (scriptId?: string) =>
    request<any>(withScript("/api/book/kpi/trends", scriptId)),
  costAlerts: (budget_usd: number | null) =>
    request<any>("/api/book/cost-alerts", {
      method: "POST",
      body: JSON.stringify({ budget_usd }),
    }),
  listHighlights: (scriptId?: string) =>
    request<any>(withScript("/api/highlights", scriptId)),
  listCharacterRuntime: (scriptId?: string) =>
    request<any>(withScript("/api/characters/runtime", scriptId)),

  listForeshadowing: (currentChapter?: number, scriptId?: string) =>
    request<{ items: ForeshadowingItem[]; stats: Record<string, number> }>(
      withScript(
        `/api/foreshadowing${currentChapter ? `?current_chapter=${currentChapter}` : ""}`,
        scriptId
      )
    ),
  upsertForeshadowing: (item: ForeshadowingItem, scriptId?: string) =>
    request<Record<string, unknown>>(withScript("/api/foreshadowing", scriptId), {
      method: "POST",
      body: JSON.stringify(item),
    }),
  deleteForeshadowing: (id: string, scriptId?: string) =>
    request<{ ok: boolean }>(
      withScript(`/api/foreshadowing/${encodeURIComponent(id)}`, scriptId),
      {
      method: "DELETE",
      }
    ),

  listFeedback: (scriptId?: string) =>
    request<{ items: Array<{ chapter: number; text: string }> }>(
      withScript("/api/feedback", scriptId)
    ),
  saveFeedback: (chapter: number, text: string, scriptId?: string) =>
    request<{ ok: boolean; chapter: number }>(withScript("/api/feedback", scriptId), {
      method: "POST",
      body: JSON.stringify({ chapter, text }),
    }),

  getTitles: (chapter: number, scriptId?: string) =>
    request<{ chapter: number; candidates: TitleCandidate[] }>(
      withScript(`/api/marketing/titles/${chapter}`, scriptId)
    ),
  getSynopsis: (scriptId?: string) =>
    request<{ text: string }>(withScript("/api/marketing/synopsis", scriptId)),
  saveSynopsis: (text: string, scriptId?: string) =>
    request<{ ok: boolean; chars: number }>(withScript("/api/marketing/synopsis", scriptId), {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
};

export function openEventStream({
  onSnapshot,
  onRunUpdate,
  onEvent,
}: {
  onSnapshot?: (runs: RunSummary[]) => void;
  onRunUpdate?: (run: RunSummary) => void;
  onEvent?: (event: TraceEvent) => void;
}): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws`);

  ws.onmessage = (msg) => {
    const payload = JSON.parse(msg.data);
    if (payload.kind === "snapshot") onSnapshot?.(payload.runs);
    if (payload.kind === "run_update") onRunUpdate?.(payload.run);
    if (payload.kind === "event") onEvent?.(payload.event);
  };

  return ws;
}
