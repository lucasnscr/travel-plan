import { create } from "zustand";
import { usePlanStore } from "./plan-store";
import type { HotelOption, Activity, WeatherForecast } from "@/types/core";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type MessageRole = "user" | "assistant";

export type AttachmentType = "hotels" | "activities" | "weather" | "actions";

export interface ChatAttachment {
  type: AttachmentType;
  data: HotelOption[] | Activity[] | WeatherForecast[] | string[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  attachments?: ChatAttachment[];
  isStreaming?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Mock responses                                                     */
/* ------------------------------------------------------------------ */

const MOCK_RESPONSES: Record<string, string> = {
  default: `I'd be happy to help you plan your trip! Here's what I found based on your preferences:\n\n**Key highlights:**\n- Great selection of hotels in your price range\n- Several highly-rated activities available\n- Weather looks favorable for your dates\n\nTake a look at the options below and let me know if you'd like any changes.`,
  hotels: `I found several excellent hotel options for you. Here are the top picks based on **location**, **reviews**, and **value for money**:\n\nEach hotel has been scored against your budget and preferences. You can select your favorite directly from the cards below.`,
  activities: `Here are some amazing activities I discovered for your trip! I've curated these based on your interests and the local weather forecast.\n\nYou can **add activities to your itinerary** directly from the cards below.`,
  weather: `Here's the weather forecast for your travel dates. I've analyzed the conditions to help you plan outdoor vs indoor activities accordingly.\n\n> **Tip**: I've already optimized your itinerary to avoid scheduling outdoor activities on rainy days.`,
  budget: `Looking at your budget, here's the breakdown:\n\n- The current plan is within your budget\n- I've found some ways to optimize spending\n- Premium options are available if you have flexibility\n\nLet me know if you'd like me to adjust anything!`,
  greeting: `Hello! I'm your AI travel planning assistant. I can help you:\n\n- **Plan a new trip** — just tell me where and when\n- **Find hotels** near specific locations\n- **Discover activities** based on your interests\n- **Optimize your itinerary** for the best experience\n\nWhat would you like to do?`,
};

const STATUS_STAGES = [
  "Understanding your request...",
  "Searching for options...",
  "Analyzing results...",
  "Building recommendations...",
  "Finalizing response...",
];

function pickResponse(userMsg: string): { text: string; attachmentTypes: AttachmentType[] } {
  const lower = userMsg.toLowerCase();

  if (lower.match(/^(hi|hello|hey|oi|ol[áa])/)) {
    return { text: MOCK_RESPONSES.greeting!, attachmentTypes: [] };
  }
  if (lower.includes("hotel") || lower.includes("hospedagem") || lower.includes("accommodation")) {
    return { text: MOCK_RESPONSES.hotels!, attachmentTypes: ["hotels"] };
  }
  if (lower.includes("atividad") || lower.includes("activit") || lower.includes("things to do")) {
    return { text: MOCK_RESPONSES.activities!, attachmentTypes: ["activities"] };
  }
  if (lower.includes("clima") || lower.includes("weather") || lower.includes("tempo")) {
    return { text: MOCK_RESPONSES.weather!, attachmentTypes: ["weather"] };
  }
  if (lower.includes("budget") || lower.includes("or[çc]amento") || lower.includes("custo")) {
    return { text: MOCK_RESPONSES.budget!, attachmentTypes: [] };
  }

  // Default: show everything if plan exists
  return { text: MOCK_RESPONSES.default!, attachmentTypes: ["hotels", "activities", "weather", "actions"] };
}

function buildAttachments(types: AttachmentType[]): ChatAttachment[] {
  const plan = usePlanStore.getState().response?.plan;
  if (!plan) return [];

  const attachments: ChatAttachment[] = [];

  for (const type of types) {
    switch (type) {
      case "hotels":
        if (plan.hotel_options.length > 0) {
          attachments.push({ type: "hotels", data: plan.hotel_options.slice(0, 3) });
        }
        break;
      case "activities":
        if (plan.activity_options.length > 0) {
          attachments.push({ type: "activities", data: plan.activity_options.slice(0, 4) });
        }
        break;
      case "weather":
        if (plan.destination_analysis?.forecast) {
          attachments.push({ type: "weather", data: plan.destination_analysis.forecast.slice(0, 5) });
        }
        break;
      case "actions":
        attachments.push({
          type: "actions",
          data: ["Add to itinerary", "View alternatives", "Confirm plan"],
        });
        break;
    }
  }

  return attachments;
}

/* ------------------------------------------------------------------ */
/*  Store                                                              */
/* ------------------------------------------------------------------ */

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  statusMessage: string | null;

  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (content: string) => void;
  finalizeStream: (attachments?: ChatAttachment[]) => void;
  setStatusMessage: (msg: string | null) => void;
  clearMessages: () => void;
  sendMessage: (content: string) => void;
}

let streamTimer: ReturnType<typeof setInterval> | null = null;
let statusTimer: ReturnType<typeof setInterval> | null = null;

function cleanupTimers() {
  if (streamTimer) { clearInterval(streamTimer); streamTimer = null; }
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  statusMessage: null,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content };
      }
      return { messages: msgs };
    }),

  finalizeStream: (attachments) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = {
          ...last,
          isStreaming: false,
          attachments: attachments && attachments.length > 0 ? attachments : last.attachments,
        };
      }
      return { messages: msgs, isStreaming: false, statusMessage: null };
    }),

  setStatusMessage: (msg) => set({ statusMessage: msg }),

  clearMessages: () => {
    cleanupTimers();
    set({ messages: [], isStreaming: false, statusMessage: null });
  },

  sendMessage: (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || get().isStreaming) return;

    cleanupTimers();

    // 1. Add user message
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: Date.now(),
    };

    // 2. Prepare response
    const { text: fullResponse, attachmentTypes } = pickResponse(trimmed);

    // 3. Add empty assistant message
    const assistantMsg: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      isStreaming: true,
    };

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      isStreaming: true,
      statusMessage: STATUS_STAGES[0] ?? null,
    }));

    // 4. Cycle status messages
    let statusIdx = 0;
    statusTimer = setInterval(() => {
      statusIdx++;
      if (statusIdx < STATUS_STAGES.length) {
        set({ statusMessage: STATUS_STAGES[statusIdx] ?? null });
      }
    }, 1500);

    // 5. Stream tokens
    let charIdx = 0;
    streamTimer = setInterval(() => {
      charIdx += 2 + Math.floor(Math.random() * 3);
      const partial = fullResponse.slice(0, charIdx);

      get().updateLastAssistant(partial);

      if (charIdx >= fullResponse.length) {
        cleanupTimers();
        const attachments = buildAttachments(attachmentTypes);
        get().finalizeStream(attachments);
      }
    }, 25);
  },
}));
