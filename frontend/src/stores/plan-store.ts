import { create } from "zustand";
import type { PlanRequest, PlanResponse } from "@/types/api";
import { planTrip, approvePlan } from "@/services/rest";

interface PlanState {
  request: PlanRequest | null;
  response: PlanResponse | null;
  isPlanning: boolean;
  error: string | null;

  submitPlan: (req: PlanRequest) => Promise<void>;
  approve: (feedback?: string) => Promise<string>;
  reject: (feedback: string) => Promise<string>;
  clearPlan: () => void;
  toggleActivity: (activityId: string) => void;
  selectHotel: (hotelId: string) => void;
}

export const usePlanStore = create<PlanState>((set) => ({
  request: null,
  response: null,
  isPlanning: false,
  error: null,

  submitPlan: async (req) => {
    set({ request: req, isPlanning: true, error: null, response: null });
    try {
      const response = await planTrip(req);
      set({ response, isPlanning: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Planning failed",
        isPlanning: false,
      });
    }
  },

  approve: async (feedback = "") => {
    const res = await approvePlan("approved", feedback);
    return res.message;
  },

  reject: async (feedback) => {
    const res = await approvePlan("rejected", feedback);
    return res.message;
  },

  clearPlan: () => {
    set({ request: null, response: null, isPlanning: false, error: null });
  },

  toggleActivity: (activityId) =>
    set((s) => {
      if (!s.response) return s;
      const ids = s.response.plan.selected_activity_ids;
      const updated = ids.includes(activityId)
        ? ids.filter((id) => id !== activityId)
        : [...ids, activityId];
      return {
        response: {
          ...s.response,
          plan: {
            ...s.response.plan,
            selected_activity_ids: updated,
          },
        },
      };
    }),

  selectHotel: (hotelId) =>
    set((s) => {
      if (!s.response) return s;
      return {
        response: {
          ...s.response,
          plan: {
            ...s.response.plan,
            selected_hotel_id: hotelId,
          },
        },
      };
    }),
}));
