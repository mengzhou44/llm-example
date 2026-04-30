function AnalyzeSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden animate-pulse">
      {[0, 1, 2].map((i) => (
        <div key={i} className={`px-5 py-4 ${i < 2 ? "border-b border-gray-100" : ""}`}>
          <div className="h-2.5 bg-gray-200 rounded w-16 mb-2.5" />
          <div className="h-4 bg-gray-200 rounded w-4/5" />
        </div>
      ))}
    </div>
  );
}

export default function IssueAnalyzer({
  analyzeInput, setAnalyzeInput,
  analyzing, analyzeResult, analyzeError,
  onSubmit,
}) {
  return (
    <div className="flex-1 overflow-y-auto px-[20%] py-8 flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-[15px] font-semibold text-gray-900">Issue Analyzer</h2>
        <p className="text-[13px] text-gray-400">
          Paste a ticket description or enter a ticket ID (e.g. "analyze ticket 1001") to get a structured AI analysis.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
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

      {analyzing && !analyzeResult && <AnalyzeSkeleton />}

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
            <div key={label} className={`px-5 py-4 ${i < arr.length - 1 ? "border-b border-gray-100" : ""}`}>
              <p className="text-[11px] uppercase tracking-widest text-gray-400 mb-1">{label}</p>
              <p className="text-[15px] text-gray-700 leading-relaxed">{value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
