import KnowledgeBase from "./KnowledgeBase";

export default function Sidebar({
  streaming,
  documents, uploading, kbError,
  onUpload, onDelete,
  onClearChat,
  fileInputRef,
}) {
  return (
    <aside className="w-60 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col gap-5 p-5">
      <h1 className="text-lg font-semibold text-gray-900">AI Chat</h1>

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
    </aside>
  );
}
