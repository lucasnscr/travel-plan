import { Link } from "react-router-dom";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Button } from "@/components/ui/Button";
import { Compass } from "lucide-react";

export function NotFoundPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <GlassPanel className="flex flex-col items-center gap-4 py-12 text-center">
        <Compass className="h-16 w-16 text-slate-600" />
        <h2 className="font-heading text-2xl font-bold text-slate-200">
          Lost your way?
        </h2>
        <p className="text-sm text-slate-500">
          This page doesn't exist, but we can help you plan a trip.
        </p>
        <Link to="/">
          <Button>Return to Planner</Button>
        </Link>
      </GlassPanel>
    </div>
  );
}
