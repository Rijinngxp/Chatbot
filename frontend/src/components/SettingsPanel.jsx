import Icon from "./Icons.jsx";

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
