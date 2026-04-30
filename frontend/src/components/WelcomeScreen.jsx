const SUGGESTED_PROMPTS = [
  "List all open tickets",
  "Analyze ticket 1001",
  "What can you help me with?",
];

export default function WelcomeScreen({ onSelectPrompt }) {
  return (
    <div className="flex flex-col items-center gap-4 mt-[20vh]">
      <p className="text-gray-400 text-[15px]">Send a message to get started.</p>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSelectPrompt(prompt)}
            className="px-3 py-1.5 rounded-full border border-gray-200 text-[13px] text-gray-600 bg-white hover:bg-gray-50 hover:border-gray-300 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
