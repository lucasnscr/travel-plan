import { create } from "zustand";
import type { ItineraryDay, ItinerarySlot, Activity } from "@/types/core";
import type { EnrichedSlot, DayTotals } from "@/components/Timeline/timeline-types";
import { updateItinerary } from "@/services/rest";

// Debounced persist to backend
let persistTimer: ReturnType<typeof setTimeout> | null = null;
const PERSIST_DEBOUNCE_MS = 500;

function schedulePersist(planId: string, days: ItineraryDay[]) {
  if (persistTimer) clearTimeout(persistTimer);
  persistTimer = setTimeout(() => {
    // Convert ItineraryDay[] to the API format (simplified DayPlan[])
    const apiDays = days.map((d) => ({
      date: d.date,
      day_number: d.day_number,
      theme: d.theme || "",
      activities: [],
    }));
    updateItinerary(planId, apiDays).catch(() => {
      // Silently ignore — local state is still valid
    });
  }, PERSIST_DEBOUNCE_MS);
}

interface TimelineState {
  /** Working copy of itinerary days (supports reordering) */
  days: ItineraryDay[];
  /** Collapsed state per day number */
  collapsedDays: Set<number>;
  /** Activity lookup for enrichment */
  activityMap: Map<string, Activity>;
  /** Currently dragging slot ID */
  draggingId: string | null;
  /** Plan ID for persistence */
  planId: string | null;

  /** Load itinerary data from plan */
  loadItinerary: (days: ItineraryDay[], activities: Activity[], planId?: string) => void;
  /** Toggle day collapse */
  toggleDay: (dayNumber: number) => void;
  /** Set dragging state */
  setDragging: (id: string | null) => void;
  /** Reorder a slot within a day */
  reorderSlot: (dayNumber: number, fromIndex: number, toIndex: number) => void;
  /** Move a slot between days */
  moveSlot: (
    fromDay: number,
    fromIndex: number,
    toDay: number,
    toIndex: number,
  ) => void;
}

export const useTimelineStore = create<TimelineState>((set) => ({
  days: [],
  collapsedDays: new Set(),
  activityMap: new Map(),
  draggingId: null,
  planId: null,

  loadItinerary: (days, activities, planId) =>
    set({
      days: days.map((d) => ({ ...d, slots: [...d.slots] })),
      activityMap: new Map(activities.map((a) => [a.id, a])),
      collapsedDays: new Set(),
      draggingId: null,
      planId: planId ?? null,
    }),

  toggleDay: (dayNumber) =>
    set((s) => {
      const next = new Set(s.collapsedDays);
      if (next.has(dayNumber)) {
        next.delete(dayNumber);
      } else {
        next.add(dayNumber);
      }
      return { collapsedDays: next };
    }),

  setDragging: (id) => set({ draggingId: id }),

  reorderSlot: (dayNumber, fromIndex, toIndex) =>
    set((s) => {
      const days = s.days.map((d) => {
        if (d.day_number !== dayNumber) return d;
        const slots = [...d.slots];
        const [moved] = slots.splice(fromIndex, 1);
        if (moved) slots.splice(toIndex, 0, moved);
        return { ...d, slots };
      });
      if (s.planId) schedulePersist(s.planId, days);
      return { days };
    }),

  moveSlot: (fromDay, fromIndex, toDay, toIndex) =>
    set((s) => {
      const days = s.days.map((d) => ({ ...d, slots: [...d.slots] }));
      const srcDay = days.find((d) => d.day_number === fromDay);
      const dstDay = days.find((d) => d.day_number === toDay);
      if (!srcDay || !dstDay) return s;

      const [moved] = srcDay.slots.splice(fromIndex, 1);
      if (moved) dstDay.slots.splice(toIndex, 0, moved);
      if (s.planId) schedulePersist(s.planId, days);
      return { days };
    }),
}));

// --- Selectors / helpers ---

/** Parse "HH:MM" into minutes from midnight */
function parseTime(t: string): number {
  const parts = t.split(":");
  return (parseInt(parts[0] ?? "0", 10)) * 60 + (parseInt(parts[1] ?? "0", 10));
}

/** Detect time conflicts within a day's slots */
export function detectConflicts(slots: ItinerarySlot[]): Set<number> {
  const conflicts = new Set<number>();
  for (let i = 0; i < slots.length; i++) {
    const a = slots[i]!;
    const aEnd = parseTime(a.end_time);
    for (let j = i + 1; j < slots.length; j++) {
      const b = slots[j]!;
      const bStart = parseTime(b.start_time);
      const bEnd = parseTime(b.end_time);
      const aStart = parseTime(a.start_time);
      // Overlap: a.start < b.end && b.start < a.end
      if (aStart < bEnd && bStart < aEnd) {
        conflicts.add(i);
        conflicts.add(j);
      }
    }
  }
  return conflicts;
}

/** Enrich slots with activity data and conflict status */
export function enrichSlots(
  day: ItineraryDay,
  activityMap: Map<string, Activity>,
): EnrichedSlot[] {
  const conflicts = detectConflicts(day.slots);

  return day.slots.map((slot, i) => {
    const activity = activityMap.get(slot.activity_id) ?? null;
    const isSelected = activity !== null; // If we have data, it's confirmed
    return {
      ...slot,
      activity,
      markerId: `act-${slot.activity_id}-d${day.day_number}`,
      dragId: `slot-${day.day_number}-${i}`,
      dayNumber: day.day_number,
      slotIndex: i,
      status: conflicts.has(i)
        ? "conflict"
        : isSelected
          ? "confirmed"
          : "pending",
    };
  });
}

/** Compute totals for a day */
export function computeDayTotals(
  slots: EnrichedSlot[],
): DayTotals {
  let totalCost = 0;
  let totalDuration = 0;
  let totalTravel = 0;
  let currency = "USD";

  for (const slot of slots) {
    if (slot.activity) {
      totalCost += slot.activity.price;
      totalDuration += slot.activity.duration_minutes;
      currency = slot.activity.currency || currency;
    }
    totalTravel += slot.travel_time_from_previous_minutes;
  }

  return { totalCost, totalDuration, totalTravel, currency };
}
