import { Footprints, Car, Bus } from "lucide-react";
import { formatDuration } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { TransportMode } from "./timeline-types";

interface TransportSegmentProps {
  travelMinutes: number;
  className?: string;
}

function inferMode(minutes: number): TransportMode {
  if (minutes <= 15) return "walk";
  if (minutes <= 90) return "car";
  return "transit";
}

const modeIcons: Record<TransportMode, typeof Car> = {
  walk: Footprints,
  car: Car,
  transit: Bus,
};

const modeLabels: Record<TransportMode, string> = {
  walk: "Walking",
  car: "Driving",
  transit: "Transit",
};

export function TransportSegment({
  travelMinutes,
  className,
}: TransportSegmentProps) {
  if (travelMinutes <= 0) return null;

  const mode = inferMode(travelMinutes);
  const Icon = modeIcons[mode];

  return (
    <div className={cn("relative flex items-center gap-2 py-1 pl-[18px]", className)}>
      {/* Dashed line continuation */}
      <div className="absolute left-[7px] top-0 h-full w-px border-l border-dashed border-white/10" />

      {/* Transport pill */}
      <div className="relative z-10 flex items-center gap-1.5 rounded-full bg-white/[0.04] px-2.5 py-1 text-[10px] text-slate-500">
        <Icon className="h-3 w-3" />
        <span>{formatDuration(travelMinutes)}</span>
        <span className="text-slate-600">{modeLabels[mode]}</span>
      </div>
    </div>
  );
}
