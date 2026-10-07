import { useEffect, useState } from "react";
import Icon from "./Icons.jsx";
import { STAGES, formatMs } from "../pipeline.js";

const STATUS_LABEL = {
  pending: "Waiting",
  running: "Running",
  done: "Complete",
  warning: "Partial",
  blocked: "Blocked",
  error: "Failed",
  skipped: "Skipped",
  stopped: "Stopped",
  answered: "Complete",
};

export default function PipelinePanel({ run }) {
  const live = run && !run.endedAt;
  const now = useNow(live);

  if (!run) {
    return (
      <div className="empty-note">
        <Icon name="layers" size={20} />
        <strong>No run yet</strong>
        <span>Ask a question and each agent's progress will appear here in real time.</span>
      </div>
    );
  }

  const total = (run.endedAt || now) - run.startedAt;
  const lastVerification = run.verifications[run.verifications.length - 1];

  return (
    <div className="panel">
      <div className="run-head">
        <div className="run-status">
          {live ? <span className="badge badge-live"><span className="live-dot" /> Live</span> : <OutcomeBadge outcome={run.outcome} />}
          <span className="run-time"><Icon name="clock" size={13} /> {formatMs(total)}</span>
        </div>
        <p className="run-question" title={run.question}>{run.question}</p>
        <div className="run-tags">
          {run.route === "unsafe" ? (
            <span className="tag tag-blocked"><Icon name="shield" size={12} /> Blocked by safety check</span>
          ) : run.route === "greeting" ? (
            <span className="tag tag-fast"><Icon name="sparkles" size={12} /> Greeting · fast path</span>
          ) : run.route === "memory" ? (
            <span className="tag tag-fast"><Icon name="bookmark" size={12} /> Answered from memory</span>
          ) : run.webSearch ? (
            <span className="tag"><Icon name="globe" size={12} /> Web search</span>
          ) : (
            <span className="tag"><Icon name="database" size={12} /> Knowledge base</span>
          )}
        </div>
      </div>

      <ol className="stepper">
        {STAGES.map((stage, i) => {
          const s = run.stages[stage.key];
          const dur = s.start ? (s.end || now) - s.start : null;
          return (
            <li key={stage.key} className={`step ${s.status}`}>
              <div className="step-rail">
                <span className="step-node">
                  {s.status === "running" ? <span className="spinner" /> : <StatusGlyph status={s.status} icon={stage.icon} />}
                </span>
                {i < STAGES.length - 1 && <span className="step-line" />}
              </div>
              <div className="step-body">
                <div className="step-title">
                  <span>{stage.label}</span>
                  {dur != null && s.status !== "skipped" && <span className="step-time">{formatMs(dur)}</span>}
                </div>
                <div className="step-desc">
                  <span className={`status-text ${s.status}`}>{STATUS_LABEL[s.status] || s.status}</span>
                  {s.detail && <> · {s.detail}</>}
                </div>

                {stage.key === "memory" && run.memories.length > 0 && (
                  <div className="step-card">
                    <span className="card-label">What I remember about you</span>
                    <ul className="memory-list">
                      {run.memories.map((m) => <li key={m.id}>{m.text}</li>)}
                    </ul>
                  </div>
                )}

                {stage.key === "planner" && run.reasoning && (
                  <div className="step-card">
                    <span className="card-label">Decision · {run.route === "unsafe" ? "blocked" : run.route}</span>
                    <span>{run.reasoning}</span>
                  </div>
                )}

                {stage.key === "planner" && run.query && run.route === "search" && (
                  <div className="step-card">
                    <span className="card-label">Search query</span>
                    <span>{run.query}</span>
                  </div>
                )}

                {stage.key === "verifier" && lastVerification && (
                  <VerifierSummary v={lastVerification} />
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="section-head">
        <span>Event log</span>
        <span className="muted">{run.log.length} events</span>
      </div>
      <ul className="event-log">
        {run.log.map((e, i) => (
          <li key={i} className={e.status}>
            <span className="ev-time">+{((e.t - run.startedAt) / 1000).toFixed(1)}s</span>
            <span className="ev-stage">{e.stage}</span>
            <span className="ev-text">{e.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function VerifierSummary({ v }) {
  const conf = typeof v.confidence === "number" ? Math.round(v.confidence * 100) : null;
  const tone = v.verdict === "approve" ? "good" : v.verdict === "block" || v.contains_explicit_content ? "bad" : "warn";
  return (
    <div className="step-card">
      <div className="verdict-row">
        <span className={`verdict ${tone}`}>{v.verdict}</span>
        {v.relevant_sources && <span className="muted small">{v.relevant_sources.length} relevant sources</span>}
        {v.unsafe_sources?.length > 0 && <span className="muted small">· {v.unsafe_sources.length} unsafe dropped</span>}
      </div>
      {conf != null && (
        <div className="meter" aria-label={`Confidence ${conf}%`}>
          <div className="meter-track"><div className={`meter-fill ${tone}`} style={{ width: `${conf}%` }} /></div>
          <span>{conf}%</span>
        </div>
      )}
      <div className="checks">
        <Check ok={v.relevant_sources ? v.relevant_sources.length > 0 : undefined} label="Relevant" />
        <Check ok={v.is_sufficient} label="Sufficient" />
        <Check ok={!v.contains_explicit_content} label="Safe" />
      </div>
      {v.explicit_categories?.length > 0 && <p className="issues-text">Flagged: {v.explicit_categories.join(", ")}</p>}
      {v.missing && <p className="issues-text">Missing: {v.missing}</p>}
    </div>
  );
}

function Check({ ok, label }) {
  if (ok === undefined) return null;
  return (
    <span className={`check ${ok ? "ok" : "fail"}`}>
      <Icon name={ok ? "check" : "x"} size={12} /> {label}
    </span>
  );
}

function StatusGlyph({ status, icon }) {
  if (status === "done") return <Icon name="check" size={13} strokeWidth={2.5} />;
  if (status === "error" || status === "blocked") return <Icon name="x" size={13} strokeWidth={2.5} />;
  if (status === "warning") return <Icon name="alert" size={12} />;
  if (status === "skipped" || status === "stopped") return <Icon name="minus" size={13} />;
  return <Icon name={icon} size={13} />;
}

function OutcomeBadge({ outcome }) {
  const map = {
    answered: ["badge-good", "Completed"],
    blocked: ["badge-bad", "Blocked"],
    error: ["badge-bad", "Failed"],
    stopped: ["badge-neutral", "Stopped"],
  };
  const [cls, label] = map[outcome] || ["badge-neutral", "Finished"];
  return <span className={`badge ${cls}`}>{label}</span>;
}

function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  return active ? now : Date.now();
}
