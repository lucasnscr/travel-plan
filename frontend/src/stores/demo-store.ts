/**
 * Demo mode state management for live presentations.
 *
 * Controls: speed, auto-play sequence, highlight tooltips, day jumping.
 * Orchestrates across plan-store, ui-store, map-store, and orchestrator-store.
 */

import { create } from "zustand";
import { DEMO_PLAN_RESPONSE, DEMO_REQUEST, DAY_CENTROIDS } from "@/utils/demo-data";
import { usePlanStore } from "@/stores/plan-store";
import { useUiStore } from "@/stores/ui-store";
import { useMapStore } from "@/stores/map-store";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { OrchestratorSocket } from "@/services/websocket";

// ─── Types ────────────────────────────────────────────────────────

export type DemoSpeed = "normal" | "demo" | "fast";

interface DemoStep {
  narration: string;
  /** Base delay in ms (scaled by speed multiplier) */
  delay: number;
  action: () => void | Promise<void>;
}

interface DemoState {
  isDemoMode: boolean;
  isPlaying: boolean;
  highlightMode: boolean;
  speed: DemoSpeed;
  currentStepIndex: number;
  currentNarration: string;
  /** Internal: reference to cancel the running sequence */
  _cancelToken: { cancelled: boolean } | null;

  toggleDemo: () => void;
  setSpeed: (s: DemoSpeed) => void;
  toggleHighlight: () => void;
  playDemo: (navigate: (path: string) => void) => Promise<void>;
  stopDemo: () => void;
  resetDemo: (navigate?: (path: string) => void) => void;
  jumpToDay: (day: number) => void;
}

// ─── Speed config ─────────────────────────────────────────────────

const SPEED_MULTIPLIERS: Record<DemoSpeed, number> = {
  fast: 0.05,
  normal: 1,
  demo: 2.5,
};

function getDelay(baseMs: number, speed: DemoSpeed): number {
  return Math.round(baseMs * SPEED_MULTIPLIERS[speed]);
}

function sleep(ms: number, token: { cancelled: boolean }): Promise<void> {
  return new Promise((resolve) => {
    if (ms <= 0 || token.cancelled) {
      resolve();
      return;
    }
    const timer = setTimeout(resolve, ms);
    // Poll for cancellation
    const check = setInterval(() => {
      if (token.cancelled) {
        clearTimeout(timer);
        clearInterval(check);
        resolve();
      }
    }, 100);
    // Clean up interval when timer fires
    setTimeout(() => clearInterval(check), ms + 50);
  });
}

// ─── Store ────────────────────────────────────────────────────────

export const useDemoStore = create<DemoState>((set, get) => ({
  isDemoMode: false,
  isPlaying: false,
  highlightMode: false,
  speed: "demo",
  currentStepIndex: -1,
  currentNarration: "",
  _cancelToken: null,

  toggleDemo: () =>
    set((s) => {
      const next = !s.isDemoMode;
      if (!next) {
        // Exiting demo mode — clean up
        return {
          isDemoMode: false,
          isPlaying: false,
          highlightMode: false,
          currentStepIndex: -1,
          currentNarration: "",
          _cancelToken: s._cancelToken
            ? { ...s._cancelToken, cancelled: true }
            : null,
        };
      }
      return { isDemoMode: true, currentNarration: "Demo mode ativado. Pressione Play para iniciar." };
    }),

  setSpeed: (speed) => set({ speed }),

  toggleHighlight: () => set((s) => ({ highlightMode: !s.highlightMode })),

  playDemo: async (navigate) => {
    const state = get();
    if (state.isPlaying) return;

    // Cancel any previous sequence
    if (state._cancelToken) state._cancelToken.cancelled = true;

    const token = { cancelled: false };
    set({ isPlaying: true, _cancelToken: token, currentStepIndex: 0 });

    const speed = get().speed;

    const steps: DemoStep[] = [
      // Step 0: Reset
      {
        narration: "Preparando o ambiente de demonstracao...",
        delay: 800,
        action: () => {
          usePlanStore.getState().clearPlan();
          useOrchestratorStore.getState().resetPipeline();
          navigate("/");
        },
      },
      // Step 1: Show the planner
      {
        narration: "O usuario preenche destino, datas e orcamento. A IA cuida do resto.",
        delay: 2000,
        action: () => {
          // Just narration — user sees the planner form
        },
      },
      // Step 2: Load demo data
      {
        narration: "Disparando o pipeline de planejamento com LangGraph...",
        delay: 1500,
        action: () => {
          usePlanStore.setState({
            request: DEMO_REQUEST,
            response: DEMO_PLAN_RESPONSE,
            isPlanning: false,
            error: null,
          });
          navigate("/results");
        },
      },
      // Step 3: Show orchestrator
      {
        narration: "LangGraph StateGraph: 12 nos especializados orquestram o planejamento.",
        delay: 1500,
        action: () => {
          useUiStore.getState().setActiveTab("orchestrator");
        },
      },
      // Step 4: Run orchestrator simulation
      {
        narration: "Cada no e um agente: analisa destino, busca hoteis, descobre atividades...",
        delay: 3000,
        action: () => {
          const socket = new OrchestratorSocket();
          socket.simulateProgress();
          // Let it run in background
        },
      },
      // Step 5: MCP tool calls
      {
        narration: "MCP Servers (Model Context Protocol) buscando dados reais de clima, hoteis e atividades via APIs externas.",
        delay: 3000,
        action: () => {
          // Orchestrator simulation is running — narration highlights MCP
        },
      },
      // Step 6: HITL gate
      {
        narration: "Human-in-the-Loop: o plano aguarda aprovacao humana antes de prosseguir.",
        delay: 2500,
        action: () => {
          // Narration only
        },
      },
      // Step 7: Switch to plan view
      {
        narration: "Resultado: hoteis ranqueados por score, atividades curadas, itinerario otimizado.",
        delay: 2000,
        action: () => {
          useUiStore.getState().setActiveTab("plan");
        },
      },
      // Step 8: Show map — day 1
      {
        narration: "Mapa interativo: Dia 1 — Asakusa e Tokyo tradicional. Pins, rotas e clima por dia.",
        delay: 2000,
        action: () => {
          useUiStore.getState().setActiveTab("map");
          get().jumpToDay(1);
        },
      },
      // Step 9: Fly through days
      {
        narration: "Dia 2 — Shibuya, Harajuku e arte digital no teamLab Borderless.",
        delay: 2000,
        action: () => get().jumpToDay(2),
      },
      {
        narration: "Dia 3 — Palacio Imperial e Akihabara: do historico ao futurista.",
        delay: 2000,
        action: () => get().jumpToDay(3),
      },
      {
        narration: "Dia 4 — Gastronomia no Tsukiji e arte imersiva no teamLab Planets.",
        delay: 2000,
        action: () => get().jumpToDay(4),
      },
      {
        narration: "Dia 5 — Sakura no Shinjuku Gyoen e bares do Golden Gai.",
        delay: 2000,
        action: () => get().jumpToDay(5),
      },
      // Step 14: Back to plan for approval
      {
        narration: "Timeline drag-and-drop: reordene atividades e a mudanca persiste via REST API.",
        delay: 2000,
        action: () => {
          useUiStore.getState().setActiveTab("plan");
        },
      },
      // Step 15: Done
      {
        narration: "Demo completa! Pressione H para ver tooltips explicativos, ou 1-5 para navegar pelos dias.",
        delay: 0,
        action: () => {},
      },
    ];

    for (let i = 0; i < steps.length; i++) {
      if (token.cancelled) break;

      const step = steps[i]!;
      set({ currentStepIndex: i, currentNarration: step.narration });

      await step.action();

      if (token.cancelled) break;
      await sleep(getDelay(step.delay, speed), token);
    }

    set({ isPlaying: false, _cancelToken: null });
  },

  stopDemo: () => {
    const state = get();
    if (state._cancelToken) state._cancelToken.cancelled = true;
    set({ isPlaying: false, _cancelToken: null });
  },

  resetDemo: (navigate) => {
    const state = get();
    if (state._cancelToken) state._cancelToken.cancelled = true;

    usePlanStore.getState().clearPlan();
    useOrchestratorStore.getState().resetPipeline();

    set({
      isPlaying: false,
      currentStepIndex: -1,
      currentNarration: "Demo resetada. Pressione Play para iniciar novamente.",
      _cancelToken: null,
    });

    if (navigate) navigate("/");
  },

  jumpToDay: (day) => {
    const centroid = DAY_CENTROIDS[day];
    if (!centroid) return;

    const mapStore = useMapStore.getState();
    mapStore.setSelectedDay(day);
    mapStore.setViewState({
      latitude: centroid.lat,
      longitude: centroid.lng,
      zoom: 14,
    });
  },
}));
