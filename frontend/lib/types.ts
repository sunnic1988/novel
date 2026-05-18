export type AgentRunStatus =
  | "idle"
  | "queued"
  | "running"
  | "awaiting_intervention"
  | "done"
  | "error"
  | "skipped";

export type RunStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "aborted"
  | "error";

export interface AgentStatus {
  id: string;
  name: string;
  role: string;
  color: string;
  icon: string;
  model: string;
  model_kind: string;
  uses_references: boolean;
  status: AgentRunStatus;
  progress: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  llm_calls: number;
  tool_calls: number;
  latency_ms: number;
  started_at: number | null;
  completed_at: number | null;
  output_preview: string;
  last_message: string;
}

export interface RunSummary {
  run_id: string;
  script_id: string;
  script_name: string;
  chapter_num: number;
  chapter_title: string;
  mode: "live" | "mock";
  status: RunStatus;
  auto_run: boolean;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_llm_calls: number;
  agents: AgentStatus[];
  paused_at_agent: string | null;
}

export interface TraceEvent {
  id: string;
  run_id: string;
  ts: number;
  type: string;
  agent: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface StatusInfo {
  chapters_count: number;
  references_count: number;
  reference_chunks: number;
  chapter_chunks: number;
  has_api_key: boolean;
  default_mode: "live";
}

export interface ReferenceItem {
  name: string;
  size: number;
  modified: number;
  preview: string;
  char_count: number;
}

export interface RunArtifactItem {
  name: string;
  size: number;
  modified: number;
  type: string;
}

export interface ScriptItem {
  id: string;
  name: string;
  description: string;
  archived: number;
  created_at: number;
  updated_at: number;
}

export interface ForeshadowingItem {
  id?: string;
  title: string;
  planted_chapter: number;
  planned_payoff_chapter?: number | null;
  payoff_chapter?: number | null;
  status: "planted" | "payoff_due" | "paid_off" | "dropped";
  importance: "high" | "medium" | "low";
  description?: string;
  related_characters?: string[];
  notes?: string;
}

export interface TitleCandidate {
  title: string;
  angle: string;
  score: number;
}

export interface CostEstimate {
  total_cost_usd: number;
  total_tokens: number;
  breakdown: Array<{
    agent: string;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
  }>;
}

export interface BookDashboard {
  chapters_written: number;
  total_words: number;
  kpi: Record<string, number>;
  runs: {
    total: number;
    total_tokens: number;
    total_cost_usd: number;
    by_agent: Array<{
      agent: string;
      calls: number;
      prompt_tokens: number;
      completion_tokens: number;
      cost_usd: number;
    }>;
  };
  foreshadowing: {
    total: number;
    open: number;
    overdue: number;
    payoff_rate: number;
  };
}

export interface KpiTrends {
  retention: Array<{ chapter: number; value: number }>;
  hook: Array<{ chapter: number; value: number }>;
  pace: Array<{ chapter: number; value: number }>;
  immersion: Array<{ chapter: number; value: number }>;
  ai_taste: Array<{ chapter: number; value: number }>;
  excitement_peaks: Array<{ chapter: number; value: number }>;
  golden_lines: Array<{ chapter: number; value: number }>;
  word_count: Array<{ chapter: number; value: number }>;
}
