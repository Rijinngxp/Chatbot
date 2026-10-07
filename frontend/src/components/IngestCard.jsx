import { useEffect, useState } from "react";
import Icon from "./Icons.jsx";
import { INGEST_STAGES, formatBytes } from "../ingest.js";
import { formatMs } from "../pipeline.js";

// Live view of one document moving through the ingestion pipeline.
export default function IngestCard({ job, onDismiss }) {
  const live = job.status === "running";
  const [open, setOpen] = useState(true);
  const now = useNow(live);
  const total = (job.endedAt || now) - job.startedAt;

  return (
    <div className={`ingest ${job.status}`}>
      <div className="ingest-head">
        <span className="ingest-icon">
          {live ? <span className="spinner" /> : <Icon name={job.status === "done" ? "check" : "alert"} size={14} />}
        </span>
        <div className="ingest-title">
          <span className="truncate" title={job.name}>{job.name}</span>
          <small>
            {formatBytes(job.size)} · {formatMs(total)}
            {job.status === "done" && <> · {job.chunks} chunks indexed</>}
            {job.status === "error" && <> · failed</>}
          </small>
        </div>
        <button className="icon-btn" onClick={() => setOpen((o) => !o)} title={open ? "Hide steps" : "Show steps"}>
          <Icon name="chevron" size={14} className={open ? "flip" : ""} />
        </button>
        {!live && (
          <button className="icon-btn" onClick={onDismiss} title="Dismiss">
            <Icon name="x" size={14} />
          </button>
        )}
      </div>

      {job.status === "error" && <div className="ingest-error">{job.message}</div>}

      {open && (
        <ol className="ingest-steps">
          {INGEST_STAGES.map((stage) => {
            const s = job.stages[stage.key];
            const dur = s.start && s.status !== "skipped" ? (s.end || now) - s.start : null;
            return (
              <li key={stage.key} className={`istep ${s.status}`}>
                <span className="istep-node">
                  {s.status === "running" ? <span className="spinner sm" /> : <StepGlyph status={s.status} icon={stage.icon} />}
                </span>
                <div className="istep-body">
                  <div className="istep-title">
                    <span>{stage.label}</span>
                    {dur >= 50 && <span className="istep-time">{formatMs(dur)}</span>}
                  </div>
                  {s.detail && <div className="istep-detail">{s.detail}</div>}
                  {s.status === "running" && s.value != null && (
                    <div className="ibar"><div className="ibar-fill" style={{ width: `${Math.round(s.value * 100)}%` }} /></div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function StepGlyph({ status, icon }) {
  if (status === "done") return <Icon name="check" size={11} strokeWidth={3} />;
  if (status === "error") return <Icon name="x" size={11} strokeWidth={3} />;
  if (status === "skipped") return <Icon name="minus" size={11} />;
  return <Icon name={icon} size={11} />;
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
