import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const BACKEND = "http://localhost:4000";
const AUTH_TOKEN = "dev-token-123";
const TEMPLATES = ["helpful_assistant", "code_reviewer", "teacher"];

function getSessionId() {
  let id = localStorage.getItem("chat_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("chat_session_id", id);
  }
  return id;
}

function formatToolCall(tc) {
  if (tc.name === "get_support_ticket") return `Fetching support ticket #${tc.input.ticket_id}…`;
  if (tc.name === "list_support_tickets") {
    return tc.input.status ? `Listing ${tc.input.status.toLowerCase()} tickets…` : "Listing all tickets…";
  }
  if (tc.name === "update_ticket_status") return `Updating ticket #${tc.input.ticket_id} → ${tc.input.status}…`;
  return `Calling ${tc.name}…`;
}

function formatStep(step) {
  if (step === "analyzing") return "Analyzing intent…";
  if (step === "validating") return "Validating response…";
  if (step === "retrying") return "Retrying…";
  return step;
}

export default function App() {
  const [mode, setMode] = useState("chat");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [template, setTemplate] = useState("helpful_assistant");
  const [streaming, setStreaming] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [kbError, setKbError] = useState("");
  const [analyzeInput, setAnalyzeInput] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [analyzeError, setAnalyzeError] = useState("");
  const bottomRef = useRef(null);
  const sessionId = useRef(getSessionId());
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetch(`${BACKEND}/knowledge/documents`, { headers: { "X-Auth-Token": AUTH_TOKEN } })
      .then((r) => r.json())
      .then(setDocuments)
      .catch(() => {});
  }, []);

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
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setStreaming(true);

    try {
      const res = await fetch(`${BACKEND}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Auth-Token": AUTH_TOKEN },
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
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], step: null };
              return next;
            });
            streamDone = true;
            break;
          }
          const data = JSON.parse(payload);
          if (data.step) {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (data.step === "retrying") {
                next[next.length - 1] = { ...last, content: "", toolCalls: [], step: data.step };
              } else {
                next[next.length - 1] = { ...last, step: data.step };
              }
              return next;
            });
          } else if (data.source) {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], source: data.source };
              return next;
            });
          } else if (data.tool_call) {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                toolCalls: [...(last.toolCalls || []), data.tool_call],
              };
              return next;
            });
          } else if (data.delta) {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                ...next[next.length - 1],
                content: next[next.length - 1].content + data.delta,
              };
              return next;
            });
          }
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

  async function analyzeIssue(e) {
    e.preventDefault();
    const text = analyzeInput.trim();
    if (!text || analyzing) return;
    setAnalyzing(true);
    setAnalyzeResult(null);
    setAnalyzeError("");
    try {
      const res = await fetch(`${BACKEND}/analyze/issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Auth-Token": AUTH_TOKEN },
        body: JSON.stringify({ description: text }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAnalyzeResult(null);
        setAnalyzeError(data.detail || "Analysis failed");
        return;
      }
      setAnalyzeResult(data);
    } catch {
      setAnalyzeResult(null);
      setAnalyzeError("Network error");
    } finally {
      setAnalyzing(false);
    }
  }

  function clearChat() {
    const newId = crypto.randomUUID();
    localStorage.setItem("chat_session_id", newId);
    sessionId.current = newId;
    setMessages([]);
  }

  async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    e.target.value = "";
    setUploading(true);
    setKbError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${BACKEND}/knowledge/upload`, {
        method: "POST",
        headers: { "X-Auth-Token": AUTH_TOKEN },
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json();
        setKbError(err.detail || "Upload failed");
        return;
      }
      const doc = await res.json();
      setDocuments((prev) => [...prev, doc]);
    } catch {
      setKbError("Network error");
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(docId) {
    setKbError("");
    try {
      const res = await fetch(`${BACKEND}/knowledge/documents/${docId}`, {
        method: "DELETE",
        headers: { "X-Auth-Token": AUTH_TOKEN },
      });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== docId));
      } else {
        const err = await res.json();
        setKbError(err.detail || "Delete failed");
      }
    } catch {
      setKbError("Network error");
    }
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 font-sans">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col gap-5 p-5">
        <h1 className="text-lg font-semibold text-gray-900">AI Chat</h1>

        {/* Mode toggle */}
        <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
          <button
            onClick={() => setMode("chat")}
            className={`flex-1 py-1.5 transition-colors ${mode === "chat" ? "bg-blue-500 text-white" : "bg-gray-50 text-gray-600 hover:bg-gray-100"}`}
          >
            Chat
          </button>
          <button
            onClick={() => setMode("analyzer")}
            className={`flex-1 py-1.5 transition-colors ${mode === "analyzer" ? "bg-blue-500 text-white" : "bg-gray-50 text-gray-600 hover:bg-gray-100"}`}
          >
            Analyzer
          </button>
        </div>

        {mode === "chat" && (
          <>
            <div className="flex flex-col gap-2">
              <label className="text-[11px] uppercase tracking-widest text-gray-400">Template</label>
              <select
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                disabled={streaming}
                className="bg-gray-50 text-gray-800 border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none capitalize cursor-pointer disabled:opacity-50 disabled:cursor-default focus:border-gray-400"
              >
                {TEMPLATES.map((t) => (
                  <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[11px] uppercase tracking-widest text-gray-400">Knowledge Base</label>

              <input
                type="file"
                ref={fileInputRef}
                accept=".txt,.md,.pdf,.docx"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="bg-gray-50 text-gray-700 border border-gray-200 rounded-lg px-3 py-2 text-sm text-left hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-default"
              >
                {uploading ? "Uploading…" : "+ Upload document"}
              </button>

              {kbError && <p className="text-xs text-red-500">{kbError}</p>}

              {documents.length > 0 ? (
                <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5"
                    >
                      <span className="flex-1 truncate text-xs text-gray-700" title={doc.name}>
                        {doc.name}
                      </span>
                      <button
                        onClick={() => deleteDocument(doc.id)}
                        className="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0 text-sm leading-none"
                        title="Remove"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No documents uploaded</p>
              )}
            </div>

            <button
              onClick={clearChat}
              disabled={streaming}
              className="mt-auto bg-gray-50 text-gray-700 border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-left hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-default"
            >
              + New chat
            </button>
          </>
        )}
      </aside>

      {/* Main area */}
      <main className="flex flex-1 flex-col min-w-0">
        {mode === "chat" ? (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-[20%] py-8 flex flex-col gap-6">
              {messages.length === 0 && (
                <p className="text-gray-400 text-center mt-[20vh] text-[15px]">
                  Send a message to get started.
                </p>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
                >
                  {msg.role === "assistant" && streaming && i === messages.length - 1 && msg.step && (
                    <span className="text-[12px] text-gray-400 italic">
                      ↳ {formatStep(msg.step)}
                    </span>
                  )}
                  {msg.role === "assistant" && msg.toolCalls?.map((tc, j) => (
                    <span key={j} className="text-[12px] text-gray-400 italic">
                      ↳ {formatToolCall(tc)}
                    </span>
                  ))}
                  {msg.role === "user" ? (
                    <span className="bg-blue-500 text-white rounded-[18px] rounded-br-[4px] px-4 py-3 max-w-[72%] text-[15px] leading-relaxed whitespace-pre-wrap break-words">
                      {msg.content}
                    </span>
                  ) : (
                    <div className="markdown-body max-w-full">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                      {streaming && i === messages.length - 1 && (
                        <span className="cursor-blink" />
                      )}
                    </div>
                  )}
                  {msg.role === "assistant" && msg.source && (
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                        msg.source === "both"
                          ? "bg-purple-100 text-purple-600"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {msg.source === "both" ? "Knowledge Base + AI" : "General AI"}
                    </span>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <form
              onSubmit={sendMessage}
              className="flex items-end gap-2 px-[20%] py-4 border-t border-gray-200 bg-white"
            >
              <textarea
                ref={textareaRef}
                rows={1}
                placeholder="Message…"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 192) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); }
                }}
                disabled={streaming}
                className="flex-1 bg-gray-50 text-gray-900 border border-gray-200 rounded-xl px-4 py-3 text-[15px] font-sans resize-none outline-none max-h-48 overflow-y-auto leading-relaxed disabled:opacity-50 focus:border-gray-400 placeholder-gray-400"
              />
              <button
                type="submit"
                disabled={!input.trim() || streaming}
                className="w-10 h-10 rounded-[10px] bg-blue-500 text-white text-lg flex items-center justify-center flex-shrink-0 hover:bg-blue-600 transition-colors disabled:opacity-35 disabled:cursor-default"
              >
                ↑
              </button>
            </form>
          </>
        ) : (
          /* Issue Analyzer */
          <div className="flex-1 overflow-y-auto px-[20%] py-8 flex flex-col gap-6">
            <div className="flex flex-col gap-1">
              <h2 className="text-[15px] font-semibold text-gray-900">Issue Analyzer</h2>
              <p className="text-[13px] text-gray-400">Paste a ticket description or enter a ticket ID (e.g. "analyze ticket 1001") to get a structured AI analysis.</p>
            </div>

            <form onSubmit={analyzeIssue} className="flex flex-col gap-3">
              <textarea
                rows={6}
                placeholder="Paste ticket description, or type e.g. 'analyze ticket 1001'…"
                value={analyzeInput}
                onChange={(e) => setAnalyzeInput(e.target.value)}
                disabled={analyzing}
                className="bg-gray-50 text-gray-900 border border-gray-200 rounded-xl px-4 py-3 text-[15px] font-sans resize-none outline-none leading-relaxed disabled:opacity-50 focus:border-gray-400 placeholder-gray-400"
              />
              <button
                type="submit"
                disabled={!analyzeInput.trim() || analyzing}
                className="self-end px-5 py-2 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-35 disabled:cursor-default"
              >
                {analyzing ? "Analyzing…" : "Analyze"}
              </button>
            </form>

            {analyzeError && (
              <p className="text-sm text-red-500">{analyzeError}</p>
            )}

            {analyzeResult && (
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                {analyzeResult.ticket_id && (
                  <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
                    <span className="text-[11px] uppercase tracking-widest text-gray-400">Ticket</span>
                    <span className="text-[12px] font-medium text-gray-600">#{analyzeResult.ticket_id}</span>
                  </div>
                )}
                {[
                  { label: "Summary", value: analyzeResult.summary },
                  { label: "Root Cause", value: analyzeResult.root_cause },
                  { label: "Suggestion", value: analyzeResult.suggestion },
                ].map(({ label, value }, i, arr) => (
                  <div
                    key={label}
                    className={`px-5 py-4 ${i < arr.length - 1 ? "border-b border-gray-100" : ""}`}
                  >
                    <p className="text-[11px] uppercase tracking-widest text-gray-400 mb-1">{label}</p>
                    <p className="text-[15px] text-gray-700 leading-relaxed">{value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <footer className="text-center text-xs text-gray-400 py-2 bg-white border-t border-gray-100">
          Easy Express Solutions Inc. &copy; 2026
        </footer>
      </main>
    </div>
  );
}
