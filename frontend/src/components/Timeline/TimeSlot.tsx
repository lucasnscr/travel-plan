import { forwardRef } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Clock,
  MapPin,
  GripVertical,
  Check,
  Timer,
  AlertTriangle,
  Landmark,
  UtensilsCrossed,
  TreePine,
  Church,
  ShoppingBag,
  GlassWater,
  Waves,
  Dumbbell,
  Compass,
  Castle,
  Camera,
  Ticket,
} from "lucide-react";
import { formatCurrency, formatDuration } from "@/utils/format";
import { cn } from "@/utils/cn";
import { DAY_COLORS } from "@/components/Map/map-types";
import type { EnrichedSlot } from "./timeline-types";

interface TimeSlotProps {
  slot: EnrichedSlot;
  isLast: boolean;
  onSlotClick?: (markerId: string, activityId: string) => void;
}

const categoryIcons: Record<string, typeof Landmark> = {
  museum: Landmark,
  restaurant: UtensilsCrossed,
  food: UtensilsCrossed,
  dining: UtensilsCrossed,
  cafe: UtensilsCrossed,
  park: TreePine,
  garden: TreePine,
  nature: TreePine,
  temple: Church,
  church: Church,
  shopping: ShoppingBag,
  market: ShoppingBag,
  nightlife: GlassWater,
  bar: GlassWater,
  beach: Waves,
  sport: Dumbbell,
  tour: Compass,
  historic: Castle,
  monument: Castle,
  landmark: Landmark,
  entertainment: Ticket,
  sightseeing: Camera,
};

function getCategoryIcon(category: string) {
  const lower = category.toLowerCase();
  for (const [key, icon] of Object.entries(categoryIcons)) {
    if (lower.includes(key)) return icon;
  }
  return MapPin;
}

const statusConfig = {
  confirmed: {
    icon: Check,
    color: "text-emerald-400",
    bg: "bg-emerald-500/15",
    label: "Confirmed",
  },
  pending: {
    icon: Timer,
    color: "text-amber-400",
    bg: "bg-amber-500/15",
    label: "Pending",
  },
  conflict: {
    icon: AlertTriangle,
    color: "text-red-400",
    bg: "bg-red-500/15",
    label: "Conflict",
  },
} as const;

/** Visual slot content — also used in DragOverlay */
export const TimeSlotContent = forwardRef<
  HTMLDivElement,
  TimeSlotProps & {
    isDragging?: boolean;
    style?: React.CSSProperties;
    dragHandleProps?: Record<string, unknown>;
  }
>(function TimeSlotContent(
  { slot, isLast, onSlotClick, isDragging = false, style, dragHandleProps, ...rest },
  ref,
) {
  const category = slot.activity?.category ?? "";
  const CategoryIcon = getCategoryIcon(category);
  const status = statusConfig[slot.status];
  const StatusIcon = status.icon;

  const colorIdx = (slot.dayNumber - 1) % DAY_COLORS.length;
  const dayColor = DAY_COLORS[colorIdx] ?? "#3b82f6";

  return (
    <div
      ref={ref}
      style={style}
      className={cn(
        "relative flex gap-3",
        isDragging && "z-50 rounded-lg border border-brand-500/30 bg-surface-900/95 shadow-2xl backdrop-blur-xl p-2",
        !isDragging && "group",
      )}
      {...rest}
    >
      {/* Vertical line + dot */}
      <div className="flex flex-col items-center pt-1">
        <div
          className="h-3 w-3 shrink-0 rounded-full"
          style={{
            backgroundColor: dayColor,
            boxShadow: `0 0 0 3px ${dayColor}30`,
          }}
        />
        {!isLast && !isDragging && (
          <div className="w-px flex-1 bg-white/10" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          "flex-1 cursor-pointer",
          isDragging ? "pb-1" : "pb-4",
        )}
        onClick={() => onSlotClick?.(slot.markerId, slot.activity_id)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSlotClick?.(slot.markerId, slot.activity_id);
          }
        }}
      >
        {/* Time + status */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-brand-400">
            {slot.start_time} – {slot.end_time}
          </span>
          <span
            className={cn(
              "flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-medium",
              status.bg,
              status.color,
            )}
          >
            <StatusIcon className="h-2.5 w-2.5" />
            {status.label}
          </span>
        </div>

        {/* Main row: thumbnail + info */}
        <div className="mt-1.5 flex items-start gap-3">
          {/* Icon placeholder */}
          <div
            className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${dayColor}12` }}
          >
            <CategoryIcon className="h-5 w-5" style={{ color: dayColor }} />
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-200 line-clamp-1">
              {slot.activity_name}
            </p>

            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500">
              {slot.activity && (
                <span className="flex items-center gap-0.5">
                  <Clock className="h-2.5 w-2.5" />
                  {formatDuration(slot.activity.duration_minutes)}
                </span>
              )}
              {slot.activity && slot.activity.price > 0 && (
                <span className="text-brand-400/80">
                  {formatCurrency(slot.activity.price, slot.activity.currency)}
                </span>
              )}
              {slot.activity?.price === 0 && (
                <span className="text-emerald-400/80">Free</span>
              )}
            </div>

            {slot.notes && (
              <p className="mt-0.5 text-[10px] text-slate-600 line-clamp-1">
                {slot.notes}
              </p>
            )}
          </div>

          {/* Drag handle */}
          <div
            className={cn(
              "shrink-0 cursor-grab rounded p-1 text-slate-600 transition-opacity",
              "opacity-0 group-hover:opacity-100",
              isDragging && "opacity-100 cursor-grabbing text-slate-400",
            )}
            {...dragHandleProps}
          >
            <GripVertical className="h-4 w-4" />
          </div>
        </div>
      </div>
    </div>
  );
});

/** Sortable wrapper using dnd-kit */
export function TimeSlot({ slot, isLast, onSlotClick }: TimeSlotProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: slot.dragId });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <TimeSlotContent
      ref={setNodeRef}
      slot={slot}
      isLast={isLast}
      onSlotClick={onSlotClick}
      isDragging={false}
      style={style}
      dragHandleProps={{ ...attributes, ...listeners }}
    />
  );
}
