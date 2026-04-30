import { useState } from "react";

export default function KnowledgeBase({ documents, uploading, kbError, onUpload, onDelete, fileInputRef }) {
  const [confirmId, setConfirmId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  async function handleDelete(docId) {
    setDeletingId(docId);
    setConfirmId(null);
    await onDelete(docId);
    setDeletingId(null);
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-[11px] uppercase tracking-widest text-gray-400">Issue Documents</label>

      <input
        type="file"
        ref={fileInputRef}
        accept=".txt,.md,.pdf,.docx"
        onChange={onUpload}
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
              {confirmId === doc.id ? (
                <span className="flex items-center gap-1 flex-shrink-0">
                  <span className="text-[11px] text-gray-500">Sure?</span>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={deletingId === doc.id}
                    className="text-red-500 hover:text-red-700 text-xs font-medium disabled:opacity-50"
                  >
                    {deletingId === doc.id ? "…" : "Yes"}
                  </button>
                  <button
                    onClick={() => setConfirmId(null)}
                    className="text-gray-400 hover:text-gray-600 text-xs"
                  >
                    No
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => setConfirmId(doc.id)}
                  disabled={deletingId === doc.id}
                  className="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0 text-sm leading-none disabled:opacity-50"
                  title="Remove"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-400">No documents uploaded yet</p>
      )}
    </div>
  );
}
