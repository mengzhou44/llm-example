import { useEffect, useRef, useState } from "react";

const BACKEND = "http://localhost:4000";
const TEMPLATES = ["helpful_assistant", "code_reviewer", "teacher"];

function getSessionId() {
  let id = localStorage.getItem("chat_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("chat_session_id", id);
  }
  return id;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [template, setTemplate] = useState("helpful_assistant");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef(null);
  const sessionId = useRef(getSessionId());

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg = { role: "user", content: text };
    const assistantMsg = { role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${BACKEND}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId.current,
          template,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content: `Error: ${err.detail}` };
          return next;
        });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") break;
          const { delta } = JSON.parse(payload);
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: "assistant",
              content: next[next.length - 1].content + delta,
            };
            return next;
          });
        }
      }
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: "Network error." };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  }

  function clearChat() {
    const newId = crypto.randomUUID();
    localStorage.setItem("chat_session_id", newId);
    sessionId.current = newId;
    setMessages([]);
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1 className="logo">AI Chat</h1>
        <div className="sidebar-section">
          <label className="sidebar-label">Template</label>
          <select
            className="select"
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            disabled={streaming}
          >
            {TEMPLATES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <button className="new-chat-btn" onClick={clearChat} disabled={streaming}>
          + New chat
        </button>
      </aside>

      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">Send a message to get started.</div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <span className="bubble">{msg.content}</span>
              {msg.role === "assistant" && streaming && i === messages.length - 1 && (
                <span className="cursor" />
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form className="input-row" onSubmit={sendMessage}>
          <textarea
            className="input"
            rows={1}
            placeholder="Message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
              }
            }}
            disabled={streaming}
          />
          <button className="send-btn" type="submit" disabled={!input.trim() || streaming}>
            ↑
          </button>
        </form>
      </main>
    </div>
  );
}
