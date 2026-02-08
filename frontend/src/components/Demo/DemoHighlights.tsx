/**
 * Highlight tooltips for demo mode.
 * Renders positioned tooltip bubbles over elements marked with data-demo-highlight.
 */

import { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Info } from "lucide-react";

interface HighlightEntry {
  key: string;
  text: string;
  rect: DOMRect;
}

const HIGHLIGHT_TEXTS: Record<string, string> = {
  orchestrator:
    "LangGraph StateGraph com 12 nos orquestrando agentes especializados em paralelo",
  map:
    "Mapa interativo com pins por dia, rotas coloridas e previsao do tempo em tempo real",
  timeline:
    "Drag-and-drop: reordene atividades e a mudanca persiste via REST API (PATCH)",
  approval:
    "Human-in-the-Loop: o humano decide aprovar ou rejeitar o plano gerado pela IA",
  hotels:
    "Hoteis ranqueados por score: preco, avaliacao, distancia e amenidades via MCP Server",
  activities:
    "Atividades curadas via Google Places API (MCP) com categorias, precos e horarios",
  chat:
    "Chat com streaming via WebSocket — resposta token por token em tempo real",
};

export function DemoHighlights() {
  const [entries, setEntries] = useState<HighlightEntry[]>([]);

  const computePositions = useCallback(() => {
    const els = document.querySelectorAll<HTMLElement>("[data-demo-highlight]");
    const next: HighlightEntry[] = [];

    els.forEach((el) => {
      const key = el.dataset.demoHighlight ?? "";
      const text = HIGHLIGHT_TEXTS[key];
      if (!text) return;

      const rect = el.getBoundingClientRect();
      // Only show if element is visible
      if (rect.width > 0 && rect.height > 0) {
        next.push({ key, text, rect });
      }
    });

    setEntries(next);
  }, []);

  useEffect(() => {
    computePositions();

    // Recompute on scroll/resize
    window.addEventListener("scroll", computePositions, true);
    window.addEventListener("resize", computePositions);

    // Also recompute periodically for layout shifts
    const interval = setInterval(computePositions, 2000);

    return () => {
      window.removeEventListener("scroll", computePositions, true);
      window.removeEventListener("resize", computePositions);
      clearInterval(interval);
    };
  }, [computePositions]);

  return (
    <div className="pointer-events-none fixed inset-0 z-[80]">
      <AnimatePresence>
        {entries.map((entry, i) => {
          // Position tooltip to the right of the element, or above if no space
          const left = Math.min(entry.rect.right + 12, window.innerWidth - 280);
          const top = Math.max(entry.rect.top, 8);

          return (
            <motion.div
              key={entry.key}
              initial={{ opacity: 0, scale: 0.9, x: -8 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ delay: i * 0.1, duration: 0.25 }}
              className="pointer-events-auto absolute w-64"
              style={{ left, top }}
            >
              <div className="rounded-lg border border-brand-500/30 bg-surface-900/95 p-3 shadow-xl backdrop-blur-md">
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                    <span className="absolute h-3 w-3 animate-ping rounded-full bg-brand-500/40" />
                    <Info className="relative h-3.5 w-3.5 text-brand-400" />
                  </div>
                  <p className="text-xs leading-relaxed text-slate-200">
                    {entry.text}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
