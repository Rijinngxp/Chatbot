import { useRef, useState } from "react";
import Icon from "./Icons.jsx";

export default function Composer({ busy, onSend, onStop, webAvailable, memoryAvailable, placeholder, onAttach }) {
  const [text, setText] = useState("");
  const [web, setWeb] = useState(false); // on = search the web instead of your documents
  const [memory, setMemory] = useState(true); // on = recall from and save to Supermemory
  const fileRef = useRef(null);
  const inputRef = useRef(null);

  const submit = () => {
    if (!text.trim() || busy) return;
    onSend(text.trim(), web && webAvailable, memory && memoryAvailable);
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
          placeholder={placeholder || "Ask a question about your documents or the web…"}
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
            <button
              type="button"
              className={`toggle ${memory && memoryAvailable ? "on" : ""}`}
              disabled={!memoryAvailable}
              aria-pressed={memory && memoryAvailable}
              title={
                !memoryAvailable
                  ? "Memory is disabled (ENABLE_MEMORY / SUPERMEMORY_API_KEY)"
                  : memory
                    ? "Memory on: recalls what it knows about you and remembers this chat (Supermemory)"
                    : "Memory off: nothing is recalled or saved for your messages"
              }
              onClick={() => setMemory((v) => !v)}
            >
              <Icon name="bookmark" size={14} /> Memory
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
