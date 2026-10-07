const BASE = "/api";

export async function getConfig() {
  const r = await fetch(`${BASE}/config`);
  return r.json();
}

export async function listDocuments() {
  const r = await fetch(`${BASE}/documents`);
  if (!r.ok) throw new Error(await errorText(r));
  return r.json();
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${BASE}/documents`, { method: "POST", body: form });
  if (!r.ok) throw new Error(await errorText(r));
  return r.json();
}

/** Uploads a file and calls onEvent for every live ingestion step (extract, chunk, embed, store, index). */
export async function uploadDocumentStream(file, onEvent, signal) {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${BASE}/documents/stream`, { method: "POST", body: form, signal });
  if (!r.ok || !r.body) throw new Error(await errorText(r));
  await readSSE(r, onEvent);
}

export async function deleteDocument(id) {
  const r = await fetch(`${BASE}/documents/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await errorText(r));
}

/** POSTs a chat request and calls onEvent for every Server-Sent Event from the agent pipeline. */
export async function streamChat({ message, history, webSearch }, onEvent, signal) {
  const r = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, web_search: webSearch }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(await errorText(r));
  await readSSE(r, onEvent);
}

/** Reads a Server-Sent Events response body and calls onEvent with each parsed `data:` payload. */
async function readSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop();
    for (const evt of events) {
      const line = evt.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

async function errorText(r) {
  try {
    const body = await r.json();
    return body.detail || JSON.stringify(body);
  } catch {
    return `${r.status} ${r.statusText}`;
  }
}
