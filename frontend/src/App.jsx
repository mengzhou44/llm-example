import { useEffect, useRef, useState } from "react";
import ChatInput from "./components/ChatInput";
import MessageList from "./components/MessageList";
import Sidebar from "./components/Sidebar";

const BACKEND = "http://localhost:4000";
const AUTH_TOKEN = import.meta.env.VITE_AUTH_TOKEN ?? "dev-token-123";

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
  const [streaming, setStreaming] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [kbError, setKbError] = useState("");
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
        body: JSON.stringify({ message: text, session_id: sessionId.current, template: "helpful_assistant" }),
      });

      if (!res.ok) {
        const err = await res.json();
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content: `Error: ${err.detail}`, isError: true };
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
          } else if (data.analysis) {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], analysis: data.analysis, content: "" };
              return next;
            });
          } else if (data.error) {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                role: "assistant",
                content: `Error: ${data.error.message}`,
                isError: true,
              };
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
        next[next.length - 1] = {
          role: "assistant",
          content: "Network error. Please check your connection and try again.",
          isError: true,
        };
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

  function handleSelectPrompt(text) {
    setInput(text);
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 192) + "px";
    }
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 font-sans">
      <Sidebar
        streaming={streaming}
        documents={documents}
        uploading={uploading}
        kbError={kbError}
        onUpload={handleFileUpload}
        onDelete={deleteDocument}
        onClearChat={clearChat}
        fileInputRef={fileInputRef}
      />

      <main className="flex flex-1 flex-col min-w-0">
        <MessageList
          messages={messages}
          streaming={streaming}
          bottomRef={bottomRef}
          onSelectPrompt={handleSelectPrompt}
        />
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={sendMessage}
          streaming={streaming}
          textareaRef={textareaRef}
        />

        <footer className="text-center text-xs text-gray-400 py-2 bg-white border-t border-gray-100">
          Easy Express Solutions Inc. &copy; 2026
        </footer>
      </main>
    </div>
  );
}
