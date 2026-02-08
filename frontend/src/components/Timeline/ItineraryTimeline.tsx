import { useEffect, useCallback, useRef, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Badge } from "@/components/ui/Badge";
import { AlertTriangle } from "lucide-react";
import { DayColumn } from "./DayColumn";
import { TimeSlotContent } from "./TimeSlot";
import {
  useTimelineStore,
  enrichSlots,
} from "@/stores/timeline-store";
import { useMapStore } from "@/stores/map-store";
import type { OptimizedItinerary, Activity } from "@/types/core";
import type { EnrichedSlot } from "./timeline-types";

interface ItineraryTimelineProps {
  itinerary: OptimizedItinerary;
  activities: Activity[];
  planId?: string;
}

export function ItineraryTimeline({
  itinerary,
  activities,
  planId,
}: ItineraryTimelineProps) {
  const {
    days,
    collapsedDays,
    activityMap,
    loadItinerary,
    toggleDay,
    reorderSlot,
    setDragging,
  } = useTimelineStore();

  const { selectMarker, setSelectedDay, setViewState } = useMapStore();
  const markers = useMapStore((s) => s.markers);

  // Active drag state for DragOverlay
  const [activeSlot, setActiveSlot] = useState<EnrichedSlot | null>(null);

  // Load itinerary into timeline store
  useEffect(() => {
    loadItinerary(itinerary.days, activities, planId);
  }, [itinerary, activities, planId, loadItinerary]);

  // --- Scroll sync via IntersectionObserver ---
  const headerRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);

  const setHeaderRef = useCallback(
    (dayNumber: number) => (el: HTMLDivElement | null) => {
      if (el) {
        headerRefs.current.set(dayNumber, el);
      } else {
        headerRefs.current.delete(dayNumber);
      }
    },
    [],
  );

  useEffect(() => {
    observerRef.current?.disconnect();

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const dayNum = Number(
              (entry.target as HTMLElement).dataset.day,
            );
            if (!isNaN(dayNum) && dayNum > 0) {
              setSelectedDay(dayNum);
            }
          }
        }
      },
      { threshold: 0.5 },
    );

    observerRef.current = observer;
    for (const el of headerRefs.current.values()) {
      observer.observe(el);
    }

    return () => observer.disconnect();
  }, [days, setSelectedDay]);

  // --- Map sync on slot click ---
  const handleSlotClick = useCallback(
    (markerId: string, _activityId: string) => {
      selectMarker(markerId);

      // Center map on the marker
      const marker = markers.find((m) => m.id === markerId);
      if (marker) {
        setViewState({
          latitude: marker.lat,
          longitude: marker.lng,
          zoom: 15,
        });
      }
    },
    [selectMarker, markers, setViewState],
  );

  // --- Drag and drop ---
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  // Build a lookup of all enriched slots for DragOverlay
  const allEnrichedSlots = useMemo(() => {
    const result = new Map<string, EnrichedSlot>();
    for (const day of days) {
      for (const slot of enrichSlots(day, activityMap)) {
        result.set(slot.dragId, slot);
      }
    }
    return result;
  }, [days, activityMap]);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const id = String(event.active.id);
      setDragging(id);
      const slot = allEnrichedSlots.get(id) ?? null;
      setActiveSlot(slot);
    },
    [setDragging, allEnrichedSlots],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setDragging(null);
      setActiveSlot(null);

      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const activeId = String(active.id);
      const overId = String(over.id);

      // Parse drag IDs: "slot-{dayNumber}-{index}"
      const activeParts = activeId.split("-");
      const overParts = overId.split("-");

      const fromDay = parseInt(activeParts[1] ?? "0", 10);
      const fromIndex = parseInt(activeParts[2] ?? "0", 10);
      const toDay = parseInt(overParts[1] ?? "0", 10);
      const toIndex = parseInt(overParts[2] ?? "0", 10);

      if (fromDay === toDay) {
        reorderSlot(fromDay, fromIndex, toIndex);
      }
      // Cross-day moves handled via moveSlot if needed
    },
    [setDragging, reorderSlot],
  );

  const handleDragCancel = useCallback(() => {
    setDragging(null);
    setActiveSlot(null);
  }, [setDragging]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-lg font-semibold text-slate-100">
          Itinerary
        </h3>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Optimized via {itinerary.optimization_method}</span>
          {itinerary.validation_iterations > 0 && (
            <span>({itinerary.validation_iterations} iterations)</span>
          )}
        </div>
      </div>

      {/* Days with DnD */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="space-y-3">
          {days.map((day, i) => (
            <DayColumn
              key={day.date}
              day={day}
              index={i}
              activityMap={activityMap}
              collapsed={collapsedDays.has(day.day_number)}
              onToggleCollapse={() => toggleDay(day.day_number)}
              onSlotClick={handleSlotClick}
              headerRef={setHeaderRef(day.day_number)}
            />
          ))}
        </div>

        {/* Drag overlay — renders the ghost preview */}
        <DragOverlay dropAnimation={null}>
          {activeSlot && (
            <TimeSlotContent
              slot={activeSlot}
              isLast
              isDragging
            />
          )}
        </DragOverlay>
      </DndContext>

      {/* Unscheduled activities */}
      {itinerary.unscheduled_activity_ids.length > 0 && (
        <div className="space-y-2 rounded-lg bg-amber-500/5 border border-amber-500/10 p-4">
          <p className="flex items-center gap-1.5 text-sm font-medium text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            Unscheduled Activities (
            {itinerary.unscheduled_activity_ids.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {itinerary.unscheduled_activity_ids.map((id) => {
              const act = activityMap.get(id);
              return (
                <Badge
                  key={id}
                  label={act?.name ?? id}
                  variant="warning"
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Validation warnings */}
      {itinerary.validation_warnings.length > 0 && (
        <div className="space-y-1 rounded-lg bg-red-500/5 border border-red-500/10 p-3">
          {itinerary.validation_warnings.map((warning, i) => (
            <p key={i} className="flex items-start gap-1.5 text-xs text-red-400/80">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              {warning}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
