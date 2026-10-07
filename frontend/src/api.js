const BASE = "/api";
const USER_KEY = "chatbot.userId";

export const newId = () => crypto.randomUUID();

/**
 * Anonymous id for this browser, used to scope long-term memory. It is not authentication:
 * anyone who has it can read that memory, so add real login before exposing the app publicly.
 */
export function userId() {
  try {
    let id = localStorage.getItem(USER_KEY);
    if (!id) {
      id = newId();
      localStorage.setItem(USER_KEY, id);
    }
    return id;
  } catch {
    // Storage blocked (e.g. private mode): memory still works for this page load.
    return (userId.fallback ??= newId());
  }
}

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

/** What the assistant remembers about this browser's user. */
export async function getMemory() {
  const r = await fetch(`${BASE}/memory`, { headers: { "X-User-Id": userId() } });
  if (!r.ok) throw new Error(await errorText(r));
  return (await r.json()).memories;
}

/** Erases everything remembered about this browser's user. */
export async function forgetMemory() {
  const r = await fetch(`${BASE}/memory`, { method: "DELETE", headers: { "X-User-Id": userId() } });
  if (!r.ok) throw new Error(await errorText(r));
  return (await r.json()).deleted_memories;
}

/** POSTs a chat request and calls onEvent for every Server-Sent Event from the agent pipeline. */
export async function streamChat({ message, history, webSearch, conversationId }, onEvent, signal) {
  const r = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history,
      web_search: webSearch,
      user_id: userId(),
      conversation_id: conversationId,
    }),
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
