/**
 * Floating demo control panel for live presentations.
 * Shows speed controls, play/reset buttons, narration, and keyboard hints.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Play,
  Square,
  RotateCcw,
  X,
  Zap,
  Gauge,
  Rocket,
  Lightbulb,
  Eye,
} from "lucide-react";
import { useDemoStore, type DemoSpeed } from "@/stores/demo-store";
import { cn } from "@/utils/cn";
import { DemoHighlights } from "./DemoHighlights";

const SPEED_OPTIONS: { value: DemoSpeed; label: string; icon: typeof Gauge }[] = [
  { value: "fast", label: "Fast", icon: Rocket },
  { value: "normal", label: "Normal", icon: Gauge },
  { value: "demo", label: "Slow", icon: Zap },
];

export function DemoOverlay() {
  const {
    isDemoMode,
    isPlaying,
    highlightMode,
    speed,
    currentNarration,
    toggleDemo,
    setSpeed,
    toggleHighlight,
    playDemo,
    stopDemo,
    resetDemo,
  } = useDemoStore();

  const navigate = useNavigate();

  if (!isDemoMode) return null;

  return (
    <>
      {/* Highlight tooltips layer */}
      {highlightMode && <DemoHighlights />}

      {/* Control panel */}
      <motion.div
        initial={{ opacity: 0, y: 40, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 40, scale: 0.95 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="fixed bottom-4 right-4 z-[90] w-80 rounded-xl border border-brand-500/30 bg-surface-950/95 shadow-2xl backdrop-blur-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-500/20">
              <Play className="h-3 w-3 text-brand-400" />
            </div>
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Demo Mode
            </span>
          </div>
          <button
            onClick={toggleDemo}
            className="rounded-md p-1 text-slate-500 transition-colors hover:bg-white/10 hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 p-4">
          {/* Speed control */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Speed
            </p>
            <div className="flex gap-1">
              {SPEED_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSpeed(opt.value)}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors",
                    speed === opt.value
                      ? "bg-brand-500/20 text-brand-300"
                      : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
                  )}
                >
                  <opt.icon className="h-3 w-3" />
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            {isPlaying ? (
              <button
                onClick={stopDemo}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-red-500/20 py-2 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/30"
              >
                <Square className="h-3.5 w-3.5" />
                Stop
              </button>
            ) : (
              <button
                onClick={() => playDemo(navigate)}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-brand-500/20 py-2 text-xs font-medium text-brand-300 transition-colors hover:bg-brand-500/30"
              >
                <Play className="h-3.5 w-3.5" />
                Play Demo
              </button>
            )}
            <button
              onClick={() => resetDemo(navigate)}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 py-2 text-xs font-medium text-slate-400 transition-colors hover:bg-white/10 hover:text-slate-200"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={toggleHighlight}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                highlightMode
                  ? "bg-amber-500/20 text-amber-300"
                  : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200",
              )}
              title="Toggle highlight tooltips"
            >
              <Eye className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Narration */}
          <AnimatePresence mode="wait">
            {currentNarration && (
              <motion.div
                key={currentNarration}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
                className="rounded-lg border border-brand-500/10 bg-brand-500/5 p-3"
              >
                <div className="flex items-start gap-2">
                  <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" />
                  <p className="text-xs leading-relaxed text-slate-300">
                    {currentNarration}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Keyboard shortcuts */}
          <div className="space-y-1 rounded-lg bg-white/[0.03] p-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-600">
              Shortcuts
            </p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px] text-slate-500">
              <span><Kbd>D</Kbd> Exit demo</span>
              <span><Kbd>H</Kbd> Highlights</span>
              <span><Kbd>1</Kbd>-<Kbd>5</Kbd> Jump to day</span>
              <span><Kbd>O</Kbd> Orchestrator</span>
              <span><Kbd>R</Kbd> Reset</span>
              <span><Kbd>F</Kbd> Fullscreen map</span>
            </div>
          </div>
        </div>
      </motion.div>
    </>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-[16px] items-center justify-center rounded border border-white/10 bg-white/5 px-1 font-mono text-[9px] text-slate-400">
      {children}
    </kbd>
  );
}
