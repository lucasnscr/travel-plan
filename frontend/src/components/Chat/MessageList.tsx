import { useEffect, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import { MessageSquare } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { SuggestedPrompts } from "./SuggestedPrompts";
import { useChatStore } from "@/stores/chat-store";

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or streaming updates
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const showSuggestions =
    messages.length === 0 ||
    (!isStreaming &&
      messages.length > 0 &&
      messages[messages.length - 1]?.role === "assistant" &&
      !messages[messages.length - 1]?.isStreaming);

  return (
    <div className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
      {/* Empty state */}
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 pt-12 pb-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-600/10">
            <MessageSquare className="h-7 w-7 text-brand-400" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-slate-200">
              AI Travel Assistant
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              Ask me anything about your trip
            </p>
          </div>
        </div>
      )}

      {/* Messages */}
      <AnimatePresence initial={false}>
        <div className="space-y-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </div>
      </AnimatePresence>

      {/* Typing indicator */}
      {isStreaming && (
        <div className="mt-4">
          <TypingIndicator />
        </div>
      )}

      {/* Suggested prompts */}
      {showSuggestions && <SuggestedPrompts />}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </div>
  );
}
