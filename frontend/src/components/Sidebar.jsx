import Icon from "./Icons.jsx";
import DocumentsPanel from "./DocumentsPanel.jsx";
import PipelinePanel from "./PipelinePanel.jsx";
import SettingsPanel from "./SettingsPanel.jsx";

const TABS = [
  { key: "documents", label: "Documents", icon: "file" },
  { key: "pipeline", label: "Pipeline", icon: "layers" },
  { key: "settings", label: "Settings", icon: "sliders" },
];

export default function Sidebar({ tab, onTab, config, docs, run, busy }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Icon name="sparkles" size={16} /></div>
        <div>
          <div className="brand-name">Agentic RAG</div>
          <div className="brand-sub">Multi-agent research</div>
        </div>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`tab ${tab === t.key ? "active" : ""}`}
            onClick={() => onTab(t.key)}
          >
            <Icon name={t.icon} size={14} />
            {t.label}
            {t.key === "documents" && docs.items.length > 0 && <span className="tab-count">{docs.items.length}</span>}
            {t.key === "pipeline" && busy && <span className="live-dot" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-body">
        {tab === "documents" && <DocumentsPanel config={config} docs={docs} />}
        {tab === "pipeline" && <PipelinePanel run={run} />}
        {tab === "settings" && <SettingsPanel config={config} />}
      </div>
    </aside>
  );
}
