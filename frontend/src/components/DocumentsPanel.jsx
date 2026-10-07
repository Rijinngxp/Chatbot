import { useRef, useState } from "react";
import Icon from "./Icons.jsx";
import IngestCard from "./IngestCard.jsx";

const ACCEPT = ".pdf,.txt,.md,.markdown,.csv,.json,.html";

export default function DocumentsPanel({ config, docs }) {
  const [filter, setFilter] = useState("");
  const [dragging, setDragging] = useState(false);
  const [confirming, setConfirming] = useState(null);
  const fileRef = useRef(null);

  if (config && !config.error && !config.rag) {
    return <EmptyNote icon="database" title="RAG is disabled" text="Set ENABLE_RAG=true in backend/.env to manage documents." />;
  }

  const items = docs.items.filter((d) => d.filename.toLowerCase().includes(filter.toLowerCase()));
  const totalChunks = docs.items.reduce((n, d) => n + d.chunks, 0);

  return (
    <div className="panel">
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files.length) docs.upload(e.dataTransfer.files);
        }}
      >
        <div className="dropzone-icon"><Icon name="upload" size={18} /></div>
        <div className="dropzone-title">Drop files or <span className="link">browse</span></div>
        <div className="dropzone-hint">PDF, TXT, MD, CSV, JSON, HTML</div>
        <input
          ref={fileRef}
          type="file"
          multiple
          hidden
          accept={ACCEPT}
          onChange={(e) => {
            if (e.target.files.length) docs.upload(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {docs.queue.length > 0 && (
        <div className="ingest-list">
          {docs.queue.map((job) => (
            <IngestCard key={job.id} job={job} onDismiss={() => docs.dismiss(job.id)} />
          ))}
        </div>
      )}

      <div className="section-head">
        <span>Library</span>
        <span className="muted">{docs.items.length} files · {totalChunks} chunks</span>
        <button className="icon-btn" onClick={docs.refresh} aria-label="Refresh" title="Refresh">
          <Icon name="refresh" size={14} className={docs.loading ? "spin" : ""} />
        </button>
      </div>

      {docs.items.length > 3 && (
        <label className="search">
          <Icon name="search" size={14} />
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter documents" />
        </label>
      )}

      {docs.error && <div className="alert alert-error">{docs.error}</div>}

      {docs.items.length === 0 && !docs.loading ? (
        <EmptyNote icon="file" title="No documents yet" text="Upload files to build your knowledge base." />
      ) : (
        <ul className="doc-list">
          {items.map((d) => (
            <li key={d.doc_id} className="doc">
              <FileBadge name={d.filename} />
              <div className="doc-meta">
                <span className="doc-name truncate" title={d.filename}>{d.filename}</span>
                <span className="doc-sub">{d.chunks} chunks · {timeAgo(d.uploaded_at)}</span>
              </div>
              {confirming === d.doc_id ? (
                <div className="confirm">
                  <button className="btn btn-danger btn-xs" onClick={() => { docs.remove(d.doc_id); setConfirming(null); }}>
                    Delete
                  </button>
                  <button className="btn btn-ghost btn-xs" onClick={() => setConfirming(null)}>Cancel</button>
                </div>
              ) : (
                <button className="icon-btn danger-hover" onClick={() => setConfirming(d.doc_id)} aria-label={`Delete ${d.filename}`} title="Delete">
                  <Icon name="trash" size={14} />
                </button>
              )}
            </li>
          ))}
          {items.length === 0 && filter && <li className="muted small pad">No matches for “{filter}”</li>}
        </ul>
      )}
    </div>
  );
}

function FileBadge({ name }) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  const kind = { pdf: "pdf", md: "md", markdown: "md", csv: "csv", json: "json", html: "html" }[ext] || "txt";
  return <span className={`file-badge ${kind}`}>{kind.toUpperCase()}</span>;
}

function EmptyNote({ icon, title, text }) {
  return (
    <div className="empty-note">
      <Icon name={icon} size={20} />
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
