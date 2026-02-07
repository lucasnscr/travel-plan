import { Plane, Menu, X, MessageSquare } from "lucide-react";
import { useUiStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";
import { useOrchestrator } from "@/hooks/use-orchestrator";
import { cn } from "@/utils/cn";

export function Header() {
  const { sidebarOpen, toggleSidebar, toggleChat } = useUiStore();
  const { isRunning } = useOrchestrator();
  const hasMessages = useChatStore((s) => s.messages.length > 0);

  return (
    <header className="sticky top-0 z-40 glass-panel-sm border-b border-white/5 px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSidebar}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-slate-200 lg:hidden"
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-500/25">
              <Plane className="h-4 w-4 text-white" />
            </div>
            <h1 className="font-heading text-lg font-bold text-gradient">
              Travel Orchestrator
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Chat toggle */}
          <button
            onClick={toggleChat}
            className="relative rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-slate-200"
            aria-label="Toggle chat"
          >
            <MessageSquare className="h-5 w-5" />
            {hasMessages && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-brand-500" />
            )}
          </button>

          {/* Status */}
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <div
              className={cn(
                "h-2 w-2 rounded-full",
                isRunning ? "bg-brand-500 animate-node-pulse" : "bg-emerald-500",
              )}
            />
            <span>{isRunning ? "Processing" : "Ready"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
