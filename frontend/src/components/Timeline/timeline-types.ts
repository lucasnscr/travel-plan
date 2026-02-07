import type { Activity, ItinerarySlot } from "@/types/core";

/** A slot enriched with full activity data for display */
export interface EnrichedSlot extends ItinerarySlot {
  activity: Activity | null;
  /** Map marker ID for sync: `act-${activityId}-d${dayNumber}` */
  markerId: string;
  /** Unique drag ID: `slot-${dayNumber}-${index}` */
  dragId: string;
  /** Day this slot belongs to */
  dayNumber: number;
  /** Index within the day */
  slotIndex: number;
  /** Conflict status */
  status: "confirmed" | "pending" | "conflict";
}

/** Transport mode between two slots */
export type TransportMode = "walk" | "car" | "transit";

/** Derived totals for a day */
export interface DayTotals {
  totalCost: number;
  totalDuration: number;
  totalTravel: number;
  currency: string;
}
