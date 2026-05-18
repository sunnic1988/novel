import type {
  CostEstimate,
  ForeshadowingItem,
  ReferenceItem,
  RunArtifactItem,
  RunSummary,
  StatusInfo,
  TitleCandidate,
  TraceEvent,
} from "@/lib/types";

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
    throw new Error(text || `${res.status} ${res.statusText}`);
  }

  return (await res.json()) as T;
}

export const api = {
  status: () => request<StatusInfo>("/api/status"),
  listRuns: () => request<{ runs: RunSummary[] }>("/api/runs"),
  getRun: (runId: string) => request<RunSummary>(`/api/runs/${runId}`),
  getEvents: (runId: string) =>
    request<{ events: TraceEvent[] }>(`/api/runs/${runId}/events`),
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
  costEstimate: (body: object) =>
    request<CostEstimate>("/api/runs/cost-estimate", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listReferences: () => request<{ items: ReferenceItem[] }>("/api/references"),
  uploadReference: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ ok: boolean; name: string; size: number }>(
      "/api/references/upload",
      { method: "POST", body: form }
    );
  },
  deleteReference: (name: string) =>
    request<{ ok: boolean }>(`/api/references/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  ingestReferences: () =>
    request<{ ok: boolean; added_chunks: number; total_chunks: number }>(
      "/api/references/ingest",
      { method: "POST" }
    ),
  searchReferences: (q: string, n = 5) =>
    request<{ results: string[] }>(
      `/api/references/search?q=${encodeURIComponent(q)}&n=${n}`
    ),

  bookDashboard: () => request<any>("/api/book/dashboard"),
  kpiTrends: () => request<any>("/api/book/kpi/trends"),
  costAlerts: (budget_usd: number | null) =>
    request<any>("/api/book/cost-alerts", {
      method: "POST",
      body: JSON.stringify({ budget_usd }),
    }),
  listHighlights: () => request<any>("/api/highlights"),
  listCharacterRuntime: () => request<any>("/api/characters/runtime"),

  listForeshadowing: (currentChapter?: number) =>
    request<{ items: ForeshadowingItem[]; stats: Record<string, number> }>(
      `/api/foreshadowing${
        currentChapter ? `?current_chapter=${currentChapter}` : ""
      }`
    ),
  upsertForeshadowing: (item: ForeshadowingItem) =>
    request<Record<string, unknown>>("/api/foreshadowing", {
      method: "POST",
      body: JSON.stringify(item),
    }),
  deleteForeshadowing: (id: string) =>
    request<{ ok: boolean }>(`/api/foreshadowing/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  listFeedback: () => request<{ items: Array<{ chapter: number; text: string }> }>("/api/feedback"),
  saveFeedback: (chapter: number, text: string) =>
    request<{ ok: boolean; chapter: number }>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ chapter, text }),
    }),

  getTitles: (chapter: number) =>
    request<{ chapter: number; candidates: TitleCandidate[] }>(
      `/api/marketing/titles/${chapter}`
    ),
  getSynopsis: () => request<{ text: string }>("/api/marketing/synopsis"),
  saveSynopsis: (text: string) =>
    request<{ ok: boolean; chars: number }>("/api/marketing/synopsis", {
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
