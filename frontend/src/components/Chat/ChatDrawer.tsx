import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Bot, Trash2 } from "lucide-react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useUiStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/utils/cn";

export function ChatDrawer() {
  const chatOpen = useUiStore((s) => s.chatOpen);
  const setChatOpen = useUiStore((s) => s.setChatOpen);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const messagesCount = useChatStore((s) => s.messages.length);
  const clearMessages = useChatStore((s) => s.clearMessages);

  // Close on Escape
  useEffect(() => {
    if (!chatOpen) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setChatOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [chatOpen, setChatOpen]);

  return (
    <AnimatePresence>
      {chatOpen && (
        <>
          {/* Backdrop — mobile only */}
          <motion.div
            key="chat-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setChatOpen(false)}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm sm:hidden"
          />

          {/* Drawer */}
          <motion.div
            key="chat-drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-white/5 bg-surface-950/98 shadow-2xl backdrop-blur-xl sm:w-[420px]"
          >
            {/* Top accent line */}
            <div className="h-px bg-gradient-to-r from-transparent via-brand-500/50 to-transparent" />

            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500/20 to-brand-600/10">
                  <Bot className="h-4 w-4 text-brand-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">
                    AI Assistant
                  </h2>
                  <div className="flex items-center gap-1.5">
                    <div
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        isStreaming
                          ? "bg-brand-500 animate-pulse"
                          : "bg-emerald-500",
                      )}
                    />
                    <span className="text-[10px] text-slate-500">
                      {isStreaming ? "Thinking..." : "Online"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1">
                {/* Clear chat */}
                {messagesCount > 0 && (
                  <button
                    onClick={clearMessages}
                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-white/10 hover:text-slate-300"
                    aria-label="Clear chat"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}

                {/* Close */}
                <button
                  onClick={() => setChatOpen(false)}
                  className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-white/10 hover:text-slate-300"
                  aria-label="Close chat"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <MessageList />

            {/* Input */}
            <ChatInput />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
