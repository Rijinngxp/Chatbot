// Turns the backend's Server-Sent Events into a "run" object the UI can render.

export const STAGES = [
  { key: "memory", label: "Memory", icon: "bookmark", desc: "Recalls what it knows about you (Supermemory)" },
  { key: "planner", label: "Planner Agent", icon: "compass", desc: "Answer in memory, greeting or search? Writes the search query" },
  { key: "rag", label: "RAG Search", icon: "database", desc: "Hybrid search over your documents" },
  { key: "web", label: "Web Search", icon: "globe", desc: "Tavily web search" },
  { key: "verifier", label: "Verifier Agent", icon: "shield", desc: "Checks the question against the retrieved chunks" },
  { key: "synthesizer", label: "Synthesizer Agent", icon: "pen", desc: "Thinks, then writes the answer" },
];

export function newRun(question, webSearch) {
  return {
    question,
    webSearch,
    startedAt: Date.now(),
    endedAt: null,
    stages: Object.fromEntries(STAGES.map((s) => [s.key, { status: "pending", detail: "", start: null, end: null }])),
    log: [],
    route: null, // planner's decision: "greeting" | "memory" | "search" | "unsafe"
    reasoning: null, // planner's explanation
    query: null, // planner's search query
    memories: [], // facts recalled about the user before planning
    verifications: [],
    sourceCount: 0,
    outcome: null, // "answered" | "blocked" | "error" | "stopped"
  };
}

export function applyEvent(run, evt) {
  const now = Date.now();
  const r = { ...run, stages: { ...run.stages }, log: run.log };

  switch (evt.type) {
    case "stage": {
      const prev = r.stages[evt.stage] || {};
      const running = evt.status === "running";
      r.stages[evt.stage] = {
        ...prev,
        status: evt.status,
        detail: evt.detail || prev.detail,
        start: prev.start ?? now,
        end: running ? null : now,
      };
      if (evt.route) r.route = evt.route;
      if (evt.reasoning) r.reasoning = evt.reasoning;
      if (evt.query) r.query = evt.query;
      if (evt.memories) r.memories = evt.memories;
      r.log = [...r.log, { t: now, stage: evt.stage, status: evt.status, text: evt.detail || evt.status }];
      break;
    }
    case "sources":
      r.sourceCount = evt.sources.length;
      break;
    case "verification":
      r.verifications = [...r.verifications, { round: evt.round, ...evt.result }];
      break;
    case "done":
      r.outcome = evt.blocked ? "blocked" : "answered";
      r.endedAt = now;
      break;
    case "error":
      r.outcome = "error";
      r.endedAt = now;
      r.log = [...r.log, { t: now, stage: "system", status: "error", text: evt.message }];
      r.stages = Object.fromEntries(
        Object.entries(r.stages).map(([k, s]) => [k, s.status === "running" ? { ...s, status: "error", end: now } : s])
      );
      break;
  }
  return r;
}

export function finishRun(run, outcome) {
  if (run.endedAt) return run;
  const now = Date.now();
  return {
    ...run,
    outcome,
    endedAt: now,
    stages: Object.fromEntries(
      Object.entries(run.stages).map(([k, s]) => [k, s.status === "running" ? { ...s, status: outcome, end: now } : s])
    ),
  };
}

export function formatMs(ms) {
  if (ms == null) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
