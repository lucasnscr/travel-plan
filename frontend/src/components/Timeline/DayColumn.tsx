import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { DayHeader } from "./DayHeader";
import { TimeSlot } from "./TimeSlot";
import { TransportSegment } from "./TransportSegment";
import { enrichSlots, computeDayTotals } from "@/stores/timeline-store";
import type { ItineraryDay, Activity } from "@/types/core";

interface DayColumnProps {
  day: ItineraryDay;
  index: number;
  activityMap: Map<string, Activity>;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onSlotClick?: (markerId: string, activityId: string) => void;
  /** Ref callback for scroll sync IntersectionObserver */
  headerRef?: (el: HTMLDivElement | null) => void;
}

export function DayColumn({
  day,
  index,
  activityMap,
  collapsed,
  onToggleCollapse,
  onSlotClick,
  headerRef,
}: DayColumnProps) {
  const enrichedSlots = useMemo(
    () => enrichSlots(day, activityMap),
    [day, activityMap],
  );

  const totals = useMemo(() => computeDayTotals(enrichedSlots), [enrichedSlots]);

  const dragIds = useMemo(
    () => enrichedSlots.map((s) => s.dragId),
    [enrichedSlots],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35 }}
      className="space-y-1"
    >
      <DayHeader
        dayNumber={day.day_number}
        date={day.date}
        theme={day.theme}
        weatherCondition={day.weather_condition}
        totals={totals}
        slotsCount={enrichedSlots.length}
        collapsed={collapsed}
        onToggle={onToggleCollapse}
        headerRef={headerRef}
      />

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key={`day-${day.day_number}-content`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="pl-2 pt-2">
              <SortableContext
                items={dragIds}
                strategy={verticalListSortingStrategy}
              >
                {enrichedSlots.map((slot, i) => (
                  <div key={slot.dragId}>
                    {/* Transport segment between slots */}
                    {i > 0 && slot.travel_time_from_previous_minutes > 0 && (
                      <TransportSegment
                        travelMinutes={slot.travel_time_from_previous_minutes}
                      />
                    )}
                    <TimeSlot
                      slot={slot}
                      isLast={i === enrichedSlots.length - 1}
                      onSlotClick={onSlotClick}
                    />
                  </div>
                ))}
              </SortableContext>

              {/* Day notes */}
              {day.notes && (
                <p className="ml-6 border-t border-white/5 pt-2 pb-1 text-xs text-slate-500">
                  {day.notes}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
