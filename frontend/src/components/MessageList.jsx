import MessageBubble from "./MessageBubble";
import WelcomeScreen from "./WelcomeScreen";

export default function MessageList({ messages, streaming, bottomRef, onSelectPrompt }) {
  return (
    <div className="flex-1 overflow-y-auto px-[20%] py-8 flex flex-col gap-6">
      {messages.length === 0 ? (
        <WelcomeScreen onSelectPrompt={onSelectPrompt} />
      ) : (
        messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            isStreaming={streaming && i === messages.length - 1}
          />
        ))
      )}
      <div ref={bottomRef} />
    </div>
  );
}
