import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";

export function TypingIndicator() {
  const statusMessage = useChatStore((s) => s.statusMessage);

  return (
    <div className="flex items-start gap-2.5 px-1">
      {/* Avatar */}
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/5">
        <Bot className="h-3.5 w-3.5 text-slate-400" />
      </div>

      <div className="space-y-1">
        {/* Bouncing dots */}
        <div className="flex items-center gap-1 rounded-2xl rounded-bl-md bg-white/5 px-4 py-3">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-slate-400"
              animate={{ y: [0, -5, 0] }}
              transition={{
                duration: 0.6,
                repeat: Infinity,
                delay: i * 0.15,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>

        {/* Status message */}
        {statusMessage && (
          <p className="px-1 text-[10px] text-slate-600">{statusMessage}</p>
        )}
      </div>
    </div>
  );
}
