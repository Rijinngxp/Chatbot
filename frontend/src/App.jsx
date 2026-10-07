import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, getConfig, listDocuments, newId, streamChat, uploadDocumentStream } from "./api.js";
import { applyEvent, finishRun, newRun } from "./pipeline.js";
import { applyIngestEvent, failIngestJob, newIngestJob } from "./ingest.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatMessage from "./components/ChatMessage.jsx";
import Composer from "./components/Composer.jsx";
import Icon from "./components/Icons.jsx";

const SUGGESTIONS = [
  "Summarize the key points of my uploaded documents",
  "What does the refund policy say?",
  "Compare the latest news on this topic with my documents",
  "List any deadlines or dates mentioned in the files",
];

export default function App() {
  const [config, setConfig] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("documents");
  const [selectedRun, setSelectedRun] = useState(null); // index of the assistant message shown in the Pipeline tab
  const [conversationId, setConversationId] = useState(newId); // groups this chat's turns in long-term memory
  const docs = useDocuments(config);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setConfig({ error: true }));
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const updateMessage = (index, fn) =>
    setMessages((msgs) => msgs.map((m, i) => (i === index ? fn(m) : m)));

  const send = async (text, webSearch) => {
    if (!text.trim() || busy) return;
    const history = messages
      .filter((m) => m.content && !m.error)
      .map((m) => ({ role: m.role, content: m.content }));
    const index = messages.length + 1;

    setMessages((msgs) => [
      ...msgs,
      { role: "user", content: text },
      { role: "assistant", content: "", sources: [], verification: null, run: newRun(text, webSearch), done: false },
    ]);
    setSelectedRun(index);
    setTab("pipeline");
    setBusy(true);

    const onEvent = (evt) =>
      updateMessage(index, (m) => {
        const next = { ...m, run: applyEvent(m.run, evt) };
        if (evt.type === "sources") next.sources = evt.sources;
        if (evt.type === "verification") next.verification = evt.result;
        if (evt.type === "token") next.content = m.content + evt.content;
        if (evt.type === "done") Object.assign(next, { done: true, blocked: !!evt.blocked });
        if (evt.type === "error") Object.assign(next, { done: true, error: evt.message });
        return next;
      });

    abortRef.current = new AbortController();
    try {
      await streamChat({ message: text, history, webSearch, conversationId }, onEvent, abortRef.current.signal);
    } catch (e) {
      const stopped = e.name === "AbortError";
      updateMessage(index, (m) => ({ ...m, error: stopped ? null : e.message, stopped, done: true }));
      updateMessage(index, (m) => ({ ...m, run: finishRun(m.run, stopped ? "stopped" : "error") }));
    } finally {
      updateMessage(index, (m) => ({ ...m, done: true, run: finishRun(m.run, "answered") }));
      setBusy(false);
    }
  };

  const newChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setSelectedRun(null);
    setConversationId(newId());
  };

  const showPipeline = (index) => {
    setSelectedRun(index);
    setTab("pipeline");
  };

  const run = selectedRun != null ? messages[selectedRun]?.run : null;

  return (
    <div className="app">
      <Sidebar
        tab={tab}
        onTab={setTab}
        config={config}
        docs={docs}
        run={run}
        busy={busy}
      />

      <main className="main">
        <header className="topbar">
          <div className="topbar-title">
            <h1>Research Assistant</h1>
            <span className="topbar-sub">
              {docs.items.length} document{docs.items.length === 1 ? "" : "s"} indexed
              {config?.models && <> · {config.models.synthesizer}</>}
            </span>
          </div>
          <div className="topbar-actions">
            {config && !config.error && !config.groq_configured && (
              <span className="pill pill-warn"><Icon name="alert" size={13} /> GROQ_API_KEY missing</span>
            )}
            {config?.error && <span className="pill pill-error"><Icon name="alert" size={13} /> Backend offline</span>}
            <button className="btn btn-ghost" onClick={newChat} disabled={messages.length === 0}>
              <Icon name="plus" size={15} /> New chat
            </button>
          </div>
        </header>

        <div className="thread" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-mark"><Icon name="sparkles" size={22} /></div>
              <h2>What would you like to research?</h2>
              <p>
                Answers are drafted from your documents and the web, fact-checked by a verifier agent, then refined
                by a synthesizer agent. Watch every step live in the Pipeline panel.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion" onClick={() => send(s, false)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="thread-inner">
              {messages.map((m, i) => (
                <ChatMessage
                  key={i}
                  message={m}
                  onShowPipeline={() => showPipeline(i)}
                />
              ))}
            </div>
          )}
        </div>

        <Composer
          busy={busy}
          onSend={send}
          onStop={() => abortRef.current?.abort()}
          webAvailable={!!config?.web_search}
          onAttach={(files) => {
            setTab("documents"); // show the live ingestion pipeline
            docs.upload(files);
          }}
        />
      </main>
    </div>
  );
}

function useDocuments(config) {
  const [items, setItems] = useState([]);
  const [queue, setQueue] = useState([]); // live ingestion jobs, see ingest.js
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listDocuments());
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (config?.rag) refresh();
  }, [config?.rag, refresh]);

  // Uploads files one by one, streaming each ingestion step into the queue so the UI can show it live.
  const upload = async (files) => {
    const jobs = [...files].map((file) => ({ file, job: newIngestJob(file) }));
    setQueue((q) => [...jobs.map(({ job }) => job), ...q]);
    for (const { file, job } of jobs) {
      const update = (fn) => setQueue((q) => q.map((j) => (j.id === job.id ? fn(j) : j)));
      try {
        await uploadDocumentStream(file, (evt) => update((j) => applyIngestEvent(j, evt)));
      } catch (e) {
        update((j) => failIngestJob(j, e.message));
      }
      refresh(); // show the new document in the library right away
    }
  };

  const remove = async (id) => {
    try {
      await deleteDocument(id);
    } catch (e) {
      setError(e.message);
    }
    refresh();
  };

  const dismiss = (id) => setQueue((q) => q.filter((j) => j.id !== id));

  return { items, queue, loading, error, refresh, upload, remove, dismiss };
}
