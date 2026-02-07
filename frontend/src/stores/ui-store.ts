import { create } from "zustand";

type ActiveTab = "plan" | "map" | "pdf" | "review" | "orchestrator";

interface UiState {
  sidebarOpen: boolean;
  activeTab: ActiveTab;
  loadingMessage: string;
  chatOpen: boolean;

  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setActiveTab: (tab: ActiveTab) => void;
  setLoadingMessage: (msg: string) => void;
  toggleChat: () => void;
  setChatOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: false,
  activeTab: "plan",
  loadingMessage: "",
  chatOpen: false,

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setLoadingMessage: (msg) => set({ loadingMessage: msg }),
  toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
  setChatOpen: (open) => set({ chatOpen: open }),
}));
