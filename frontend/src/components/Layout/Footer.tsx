import { Sparkles } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-white/5 px-4 py-2">
      <div className="flex items-center justify-between text-[11px] text-slate-600">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3" />
          <span>Powered by AI</span>
        </div>
        <span>Travel Orchestrator v1.0</span>
      </div>
    </footer>
  );
}
