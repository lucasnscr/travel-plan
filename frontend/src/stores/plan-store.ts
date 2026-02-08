import { create } from "zustand";
import type { PlanRequest, PlanResponse } from "@/types/api";
import { planTrip, approveTrip } from "@/services/rest";
import { toast } from "@/components/ui/Toast";

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
      toast.success("Trip plan generated successfully!");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Planning failed";
      set({ error: message, isPlanning: false });
      toast.error(message);
    }
  },

  approve: async (feedback = "") => {
    const plan = usePlanStore.getState().response?.plan;
    const planId = plan?.plan_id;
    if (planId) {
      try {
        const res = await approveTrip(planId, "approved", feedback);
        toast.success("Trip approved!");
        return res.message;
      } catch {
        toast.error("Failed to approve trip");
        return "Approval failed";
      }
    }
    return "No plan to approve";
  },

  reject: async (feedback) => {
    const plan = usePlanStore.getState().response?.plan;
    const planId = plan?.plan_id;
    if (planId) {
      try {
        const res = await approveTrip(planId, "rejected", feedback);
        toast.warning("Trip plan rejected");
        return res.message;
      } catch {
        toast.error("Failed to reject trip");
        return "Rejection failed";
      }
    }
    return "No plan to reject";
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
