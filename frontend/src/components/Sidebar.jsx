import KnowledgeBase from "./KnowledgeBase";

const TEMPLATES = ["helpful_assistant", "code_reviewer", "teacher"];

export default function Sidebar({
  mode, setMode,
  template, setTemplate,
  streaming,
  documents, uploading, kbError,
  onUpload, onDelete,
  onClearChat,
  fileInputRef,
}) {
  return (
    <aside className="w-60 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col gap-5 p-5">
      <h1 className="text-lg font-semibold text-gray-900">AI Chat</h1>

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

          <KnowledgeBase
            documents={documents}
            uploading={uploading}
            kbError={kbError}
            onUpload={onUpload}
            onDelete={onDelete}
            fileInputRef={fileInputRef}
          />

          <button
            onClick={onClearChat}
            disabled={streaming}
            className="mt-auto bg-gray-50 text-gray-700 border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-left hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-default"
          >
            + New chat
          </button>
        </>
      )}
    </aside>
  );
}
