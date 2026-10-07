import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Icon from "./Icons.jsx";
import { STAGES } from "../pipeline.js";

export default function ChatMessage({ message, onShowPipeline }) {
  if (message.role === "user") {
    return (
      <div className="msg-user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }
  return <AssistantMessage message={message} onShowPipeline={onShowPipeline} />;
}

function AssistantMessage({ message, onShowPipeline }) {
  const { content, run, done, error, blocked, stopped } = message;
  const [copied, setCopied] = useState(false);
  const text = stripCitations(content);

  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const running = STAGES.find((s) => run?.stages[s.key].status === "running");

  return (
    <article className="msg-assistant">
      <div className="avatar"><Icon name="sparkles" size={15} /></div>
      <div className="msg-body">
        {!done && !content && (
          <div className="typing" onClick={onShowPipeline} title="View live pipeline">
            <span className="dots"><i /><i /><i /></span>
            <span className="typing-label">{running ? `${running.label}…` : "Thinking…"}</span>
          </div>
        )}

        {content && (
          <div className={`answer ${blocked ? "answer-blocked" : ""}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a> }}
            >
              {text}
            </ReactMarkdown>
            {!done && <span className="caret-blink" />}
          </div>
        )}

        {error && <div className="alert alert-error"><Icon name="alert" size={14} /> {error}</div>}
        {stopped && !content && <div className="muted small">Generation stopped.</div>}

        {done && content && (
          <div className="msg-actions">
            <button className="icon-btn" onClick={copy} title={copied ? "Copied" : "Copy"}>
              <Icon name={copied ? "check" : "copy"} size={14} />
            </button>
            {run && (
              <button className="icon-btn" onClick={onShowPipeline} title="View pipeline">
                <Icon name="layers" size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

// Removes source citations like [1], [2][3], 【4】 or 【4†L1-L4】 so answers read as plain chat.
function stripCitations(text) {
  return text
    .replace(/\s?【\d{1,3}(?:†[^】]*)?】/g, "")
    .replace(/\s?\[\d{1,3}\](?!\()/g, "")
    .replace(/ +([.,;:!?])/g, "$1");
}
