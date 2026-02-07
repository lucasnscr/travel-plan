import { motion } from "framer-motion";
import {
  Plane,
  Hotel,
  Compass,
  Sun,
} from "lucide-react";
import { useChatStore } from "@/stores/chat-store";

const SUGGESTIONS = [
  { text: "Plan 5 days in Tokyo", icon: Plane },
  { text: "Find hotel near city center", icon: Hotel },
  { text: "Activities for kids", icon: Compass },
  { text: "Best time to visit Paris", icon: Sun },
] as const;

export function SuggestedPrompts() {
  const sendMessage = useChatStore((s) => s.sendMessage);

  return (
    <div className="space-y-3 px-1 py-4">
      <p className="text-center text-xs text-slate-500">
        Try one of these to get started
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s, i) => {
          const Icon = s.icon;
          return (
            <motion.button
              key={s.text}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08, duration: 0.25 }}
              onClick={() => sendMessage(s.text)}
              className="flex items-center gap-1.5 rounded-full border border-brand-500/20 bg-brand-500/5 px-3 py-1.5 text-xs text-brand-400 transition-colors hover:bg-brand-500/15 hover:text-brand-300"
            >
              <Icon className="h-3 w-3" />
              {s.text}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
