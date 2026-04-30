import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function formatToolCall(tc, done) {
  const verb = (active, past) => done ? past : active;
  if (tc.name === "get_support_ticket")
    return `${verb("Fetching", "Fetched")} support ticket #${tc.input.ticket_id}${done ? "" : "…"}`;
  if (tc.name === "list_support_tickets") {
    const what = tc.input.status ? `${tc.input.status.toLowerCase()} tickets` : "all tickets";
    return `${verb("Listing", "Listed")} ${what}${done ? "" : "…"}`;
  }
  if (tc.name === "update_ticket_status")
    return `${verb("Updating", "Updated")} ticket #${tc.input.ticket_id} → ${tc.input.status}${done ? "" : "…"}`;
  return `${verb("Calling", "Called")} ${tc.name}${done ? "" : "…"}`;
}

function formatStep(step) {
  if (step === "analyzing") return "Analyzing intent…";
  if (step === "validating") return "Validating response…";
  if (step === "retrying") return "Retrying…";
  return step;
}

export default function MessageBubble({ msg, isStreaming }) {
  const toolsDone = !isStreaming;

  return (
    <div className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}>
      {msg.role === "assistant" && isStreaming && msg.step && (
        <span className="text-[12px] text-gray-400 italic">
          ↳ {formatStep(msg.step)}
        </span>
      )}
      {msg.role === "assistant" && msg.toolCalls?.map((tc, j) => (
        <span
          key={j}
          className={`text-[12px] ${toolsDone ? "text-gray-300" : "text-gray-400 italic"}`}
        >
          {toolsDone ? "✓" : "↳"} {formatToolCall(tc, toolsDone)}
        </span>
      ))}
      {msg.role === "user" ? (
        <span className="bg-blue-500 text-white rounded-[18px] rounded-br-[4px] px-4 py-3 max-w-[72%] text-[15px] leading-relaxed whitespace-pre-wrap break-words">
          {msg.content}
        </span>
      ) : msg.isError ? (
        <div className="max-w-full bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-[15px] text-red-600 leading-relaxed">
          {msg.content}
        </div>
      ) : (
        <div className="markdown-body max-w-full">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          {isStreaming && <span className="cursor-blink" />}
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
  );
}
