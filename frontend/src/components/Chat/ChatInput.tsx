import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SendHorizonal, Mic, MicOff } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";
import { usePlanStore } from "@/stores/plan-store";
import { cn } from "@/utils/cn";

/* ------------------------------------------------------------------ */
/*  SpeechRecognition type augmentation                                */
/* ------------------------------------------------------------------ */

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as SpeechRecognitionConstructor | null;
}

/* ------------------------------------------------------------------ */
/*  ChatInput                                                          */
/* ------------------------------------------------------------------ */

export function ChatInput() {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const isStreaming = useChatStore((s) => s.isStreaming);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const hasPlan = usePlanStore((s) => s.response !== null);

  const hasSpeech = typeof window !== "undefined" && getSpeechRecognition() !== null;

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  // Handle send
  const handleSend = useCallback(() => {
    if (!value.trim() || isStreaming) return;
    sendMessage(value.trim());
    setValue("");
  }, [value, isStreaming, sendMessage]);

  // Handle keydown
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Speech recognition
  const toggleRecording = useCallback(() => {
    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }

    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result) {
          const alt = result[0];
          if (alt) transcript += alt.transcript;
        }
      }
      setValue((prev) => prev + transcript);
    };

    recognition.onend = () => setRecording(false);
    recognition.onerror = () => setRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
  }, [recording]);

  // Contextual placeholder
  const placeholder = isStreaming
    ? "AI is thinking..."
    : hasPlan
      ? "Change the hotel for day 2..."
      : "Plan my trip to...";

  const canSend = value.trim().length > 0 && !isStreaming;

  return (
    <div className="border-t border-white/5 px-3 py-3">
      <div className="flex items-end gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 transition-colors focus-within:border-brand-500/30 focus-within:bg-white/[0.05]">
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isStreaming}
          rows={1}
          className="max-h-[160px] min-h-[28px] flex-1 resize-none bg-transparent text-[13px] text-slate-200 outline-none placeholder:text-slate-600 disabled:opacity-50"
        />

        {/* Mic button */}
        {hasSpeech && (
          <button
            onClick={toggleRecording}
            disabled={isStreaming}
            className={cn(
              "shrink-0 rounded-lg p-1.5 transition-colors",
              recording
                ? "bg-red-500/20 text-red-400"
                : "text-slate-500 hover:bg-white/10 hover:text-slate-300",
              isStreaming && "pointer-events-none opacity-40",
            )}
            aria-label={recording ? "Stop recording" : "Start voice input"}
          >
            <AnimatePresence mode="wait">
              {recording ? (
                <motion.div
                  key="recording"
                  initial={{ scale: 0.8 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0.8 }}
                  className="relative"
                >
                  <MicOff className="h-4 w-4" />
                  <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                </motion.div>
              ) : (
                <motion.div
                  key="idle"
                  initial={{ scale: 0.8 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0.8 }}
                >
                  <Mic className="h-4 w-4" />
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        )}

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={cn(
            "shrink-0 rounded-lg p-1.5 transition-all",
            canSend
              ? "bg-gradient-to-r from-brand-500 to-brand-600 text-white shadow-lg shadow-brand-500/25 hover:from-brand-400 hover:to-brand-500"
              : "text-slate-600",
          )}
          aria-label="Send message"
        >
          <SendHorizonal className="h-4 w-4" />
        </button>
      </div>

      <p className="mt-1.5 text-center text-[10px] text-slate-700">
        AI responses are simulated for demo purposes
      </p>
    </div>
  );
}
