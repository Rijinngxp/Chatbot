import { useState } from "react";
import Icon from "./Icons.jsx";
import { forgetMemory, getMemory } from "../api.js";

export default function SettingsPanel({ config }) {
  if (!config) return <div className="muted small pad">Loading…</div>;
  if (config.error) {
    return (
      <div className="empty-note">
        <Icon name="alert" size={20} />
        <strong>Backend unreachable</strong>
        <span>Start the API on port 8000, then reload this page.</span>
      </div>
    );
  }

  const features = [
    ["RAG retrieval", config.rag],
    ["Reranker", config.reranker],
    ["Web search", config.web_search],
    ["Verifier agent", config.verifier],
    ["Long-term memory", config.memory],
  ];

  return (
    <div className="panel">
      <p className="muted small">Read-only. Change these in <code>backend/.env</code> and restart the API.</p>

      <div className="section-head"><span>API keys</span></div>
      <div className="kv">
        <span>Groq</span>
        <span className={`status-chip ${config.groq_configured ? "on" : "off"}`}>
          {config.groq_configured ? "Configured" : "Missing"}
        </span>
      </div>

      <div className="section-head"><span>Features</span></div>
      {features.map(([label, on]) => (
        <div className="kv" key={label}>
          <span>{label}</span>
          <span className={`status-chip ${on ? "on" : "off"}`}>{on ? "Enabled" : "Disabled"}</span>
        </div>
      ))}

      {config.memory && <MemorySection />}

      <div className="section-head"><span>Models</span></div>
      {Object.entries(config.models).map(([role, model]) => (
        <div className="model-row" key={role}>
          <span className="model-role">{role}</span>
          <code className="model-name">{model}</code>
        </div>
      ))}
    </div>
  );
}

/** Shows what Supermemory remembers about this browser's user, with a way to erase it. */
function MemorySection() {
  const [memories, setMemories] = useState(null); // null = not loaded yet
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    setStatus("");
    try {
      await fn();
    } catch (e) {
      setStatus(e.message);
    } finally {
      setBusy(false);
    }
  };

  const load = () => run(async () => setMemories(await getMemory()));

  const forget = () => {
    if (!confirm("Forget everything the assistant remembers about you? This can't be undone.")) return;
    run(async () => {
      const n = await forgetMemory();
      setMemories([]);
      setStatus(`Forgot ${n} ${n === 1 ? "memory" : "memories"}.`);
    });
  };

  return (
    <>
      <div className="section-head">
        <span>Memory</span>
        {memories && <span className="muted">{memories.length} remembered</span>}
      </div>
      <p className="muted small">
        Facts the assistant learned about you in earlier chats. New facts can take a few seconds to appear.
      </p>
      {memories?.length > 0 && (
        <ul className="memory-list">
          {memories.map((m) => <li key={m.id}>{m.text}</li>)}
        </ul>
      )}
      {memories?.length === 0 && <p className="muted small">Nothing remembered yet.</p>}
      {status && <p className="muted small">{status}</p>}
      <div className="memory-actions">
        <button className="btn btn-ghost btn-xs" onClick={load} disabled={busy}>
          <Icon name="refresh" size={12} /> {memories ? "Refresh" : "Show memories"}
        </button>
        <button className="btn btn-danger btn-xs" onClick={forget} disabled={busy}>
          <Icon name="trash" size={12} /> Forget me
        </button>
      </div>
    </>
  );
}
