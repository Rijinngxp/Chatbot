import { useRef, useState } from "react";
import Icon from "./Icons.jsx";

export default function Composer({ busy, onSend, onStop, webAvailable, onAttach }) {
  const [text, setText] = useState("");
  const [web, setWeb] = useState(false); // on = search the web instead of your documents
  const fileRef = useRef(null);
  const inputRef = useRef(null);

  const submit = () => {
    if (!text.trim() || busy) return;
    onSend(text.trim(), web && webAvailable);
    setText("");
    inputRef.current?.focus();
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          ref={inputRef}
          value={text}
          rows={1}
          placeholder="Ask a question about your documents or the web…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <div className="composer-bar">
          <div className="composer-left">
            <button
              type="button"
              className={`toggle ${web && webAvailable ? "on" : ""}`}
              disabled={!webAvailable}
              aria-pressed={web && webAvailable}
              title={webAvailable ? "Search the web (Tavily) instead of your documents" : "Web search is disabled (ENABLE_WEB_SEARCH / TAVILY_API_KEY)"}
              onClick={() => setWeb((v) => !v)}
            >
              <Icon name="globe" size={14} /> Web search
            </button>
            <button type="button" className="icon-btn" title="Upload documents" onClick={() => fileRef.current?.click()}>
              <Icon name="paperclip" size={15} />
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              accept=".pdf,.txt,.md,.markdown,.csv,.json,.html"
              onChange={(e) => {
                if (e.target.files.length) onAttach(e.target.files);
                e.target.value = "";
              }}
            />
          </div>
          {busy ? (
            <button type="button" className="send stop" onClick={onStop} title="Stop">
              <Icon name="stop" size={14} />
            </button>
          ) : (
            <button type="button" className="send" onClick={submit} disabled={!text.trim()} title="Send (Enter)">
              <Icon name="send" size={16} strokeWidth={2.5} />
            </button>
          )}
        </div>
      </div>
      <div className="composer-hint">Enter to send · Shift + Enter for a new line</div>
    </div>
  );
}
