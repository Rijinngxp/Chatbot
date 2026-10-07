// Turns the backend's document-ingestion events into a "job" object the UI can render live.

export const INGEST_STAGES = [
  { key: "upload", label: "Upload", icon: "upload" },
  { key: "extract", label: "Extract text", icon: "file" },
  { key: "split", label: "Split into sentences", icon: "layers" },
  { key: "embed_sentences", label: "Embed sentences", icon: "sparkles" },
  { key: "chunk", label: "Semantic chunking", icon: "branch" },
  { key: "embed_chunks", label: "Embed chunks", icon: "sparkles" },
  { key: "store", label: "Save to ChromaDB", icon: "database" },
  { key: "index", label: "BM25 keyword index", icon: "search" },
];

export function newIngestJob(file) {
  const now = Date.now();
  const stages = Object.fromEntries(
    INGEST_STAGES.map((s) => [s.key, { status: "pending", detail: "", value: null, start: null, end: null }])
  );
  stages.upload = { status: "running", detail: "Sending file", value: null, start: now, end: null };
  return {
    id: `${file.name}-${now}-${Math.random()}`,
    name: file.name,
    size: file.size,
    status: "running", // running | done | error
    startedAt: now,
    endedAt: null,
    stages,
    chunks: null,
    message: "",
  };
}

export function applyIngestEvent(job, evt) {
  const now = Date.now();
  const j = { ...job, stages: { ...job.stages } };

  if (evt.type === "stage") {
    const prev = j.stages[evt.stage] || {};
    const running = evt.status === "running";
    j.stages[evt.stage] = {
      status: evt.status,
      detail: evt.detail || prev.detail,
      value: evt.value ?? (running ? prev.value : null),
      start: prev.start ?? now,
      end: running ? null : now,
    };
  } else if (evt.type === "done") {
    Object.assign(j, { status: "done", endedAt: now, chunks: evt.document.chunks });
  } else if (evt.type === "error") {
    Object.assign(j, { status: "error", endedAt: now, message: evt.message });
    j.stages = Object.fromEntries(
      Object.entries(j.stages).map(([k, s]) => [k, s.status === "running" ? { ...s, status: "error", end: now } : s])
    );
  }
  return j;
}

export function failIngestJob(job, message) {
  return applyIngestEvent(job, { type: "error", message });
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
