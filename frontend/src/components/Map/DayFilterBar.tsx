import { cn } from "@/utils/cn";
import { DAY_COLORS } from "./map-types";

interface DayFilterBarProps {
  totalDays: number;
  selectedDay: number | null;
  onDaySelect: (day: number | null) => void;
}

export function DayFilterBar({
  totalDays,
  selectedDay,
  onDaySelect,
}: DayFilterBarProps) {
  if (totalDays === 0) return null;

  return (
    <div className="absolute left-1/2 top-3 z-10 flex -translate-x-1/2 gap-1 overflow-x-auto rounded-xl bg-surface-950/80 p-1 backdrop-blur-lg border border-white/10 max-w-[90%]">
      <button
        onClick={() => onDaySelect(null)}
        className={cn(
          "shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
          selectedDay === null
            ? "bg-white/15 text-slate-100 shadow-sm"
            : "text-slate-400 hover:bg-white/5 hover:text-slate-300",
        )}
      >
        All
      </button>
      {Array.from({ length: totalDays }, (_, i) => {
        const day = i + 1;
        const color = DAY_COLORS[i % DAY_COLORS.length] ?? "#3b82f6";
        const active = selectedDay === day;
        return (
          <button
            key={day}
            onClick={() => onDaySelect(day)}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
              active
                ? "bg-white/15 text-slate-100 shadow-sm"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-300",
            )}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            Day {day}
          </button>
        );
      })}
    </div>
  );
}
