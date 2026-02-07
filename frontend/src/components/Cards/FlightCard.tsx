import { Plane, Clock, Leaf } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { formatCurrency, formatDuration } from "@/utils/format";
import type { FlightOption } from "@/types/core";
import { cn } from "@/utils/cn";

interface FlightCardProps {
  flight: FlightOption;
  selected?: boolean;
}

export function FlightCard({ flight, selected }: FlightCardProps) {
  return (
    <GlassPanel
      hover
      className={cn("space-y-3", selected && "ring-1 ring-brand-500/50")}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Plane className="h-4 w-4 text-brand-400" />
          <span className="font-heading font-semibold text-slate-100">
            {flight.airline}
          </span>
          <Badge label={flight.booking_class} />
        </div>
        <p className="text-lg font-bold text-brand-400">
          {formatCurrency(flight.price, flight.currency)}
        </p>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div>
          <p className="font-medium text-slate-200">{flight.departure_time}</p>
          <p className="text-xs text-slate-500">Departure</p>
        </div>
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="h-3 w-3" />
            {formatDuration(flight.duration_minutes)}
          </div>
          <div className="h-px w-24 bg-white/10" />
          <p className="text-xs text-slate-500">
            {flight.stops === 0 ? "Direct" : `${flight.stops} stop${flight.stops > 1 ? "s" : ""}`}
          </p>
        </div>
        <div className="text-right">
          <p className="font-medium text-slate-200">{flight.arrival_time}</p>
          <p className="text-xs text-slate-500">Arrival</p>
        </div>
      </div>

      <div className="flex items-center gap-1 text-xs text-slate-500">
        <Leaf className="h-3 w-3 text-emerald-500" />
        {flight.carbon_footprint_kg.toFixed(0)} kg CO2
      </div>
    </GlassPanel>
  );
}
