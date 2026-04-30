export default function ChatInput({ input, setInput, onSubmit, streaming, textareaRef }) {
  return (
    <form
      onSubmit={onSubmit}
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
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmit(e); }
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
  );
}
