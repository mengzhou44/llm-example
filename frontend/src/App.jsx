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

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${BACKEND}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId.current, template }),
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
    <div className="flex h-screen bg-[#212121] text-[#ececec] font-sans">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-[#171717] flex flex-col gap-5 p-5">
        <h1 className="text-lg font-semibold text-white">AI Chat</h1>

        <div className="flex flex-col gap-2">
          <label className="text-[11px] uppercase tracking-widest text-[#888]">Template</label>
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            disabled={streaming}
            className="bg-[#2a2a2a] text-[#ececec] border border-[#3a3a3a] rounded-lg px-3 py-2 text-sm outline-none capitalize cursor-pointer disabled:opacity-50 disabled:cursor-default focus:border-[#555]"
          >
            {TEMPLATES.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>

        <button
          onClick={clearChat}
          disabled={streaming}
          className="mt-auto bg-[#2a2a2a] text-[#ececec] border border-[#3a3a3a] rounded-lg px-4 py-2.5 text-sm text-left hover:bg-[#333] transition-colors disabled:opacity-50 disabled:cursor-default"
        >
          + New chat
        </button>
      </aside>

      {/* Chat area */}
      <main className="flex flex-1 flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-[20%] py-8 flex flex-col gap-6">
          {messages.length === 0 && (
            <p className="text-[#555] text-center mt-[20vh] text-[15px]">
              Send a message to get started.
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
            >
              <span
                className={`text-[15px] leading-relaxed whitespace-pre-wrap break-words ${
                  msg.role === "user"
                    ? "bg-[#2f2f2f] rounded-[18px] rounded-br-[4px] px-4 py-3 max-w-[72%]"
                    : "max-w-full"
                }`}
              >
                {msg.content}
                {msg.role === "assistant" && streaming && i === messages.length - 1 && (
                  <span className="cursor-blink" />
                )}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form
          onSubmit={sendMessage}
          className="flex items-end gap-2 px-[20%] py-4 border-t border-[#2a2a2a]"
        >
          <textarea
            rows={1}
            placeholder="Message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); }
            }}
            disabled={streaming}
            className="flex-1 bg-[#2f2f2f] text-[#ececec] border border-[#3a3a3a] rounded-xl px-4 py-3 text-[15px] font-sans resize-none outline-none max-h-48 overflow-y-auto leading-relaxed disabled:opacity-50 focus:border-[#555]"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="w-10 h-10 rounded-[10px] bg-[#ececec] text-[#212121] text-lg flex items-center justify-center flex-shrink-0 hover:bg-white transition-colors disabled:opacity-35 disabled:cursor-default"
          >
            ↑
          </button>
        </form>
      </main>
    </div>
  );
}
