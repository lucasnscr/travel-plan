import { useState, useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useUiStore } from "@/stores/ui-store";
import { usePlanStore } from "@/stores/plan-store";
import { usePlan } from "@/hooks/use-plan";
import { PlanSummaryCard } from "@/components/Cards/PlanSummaryCard";
import { HotelCard } from "@/components/Cards/HotelCard";
import { ActivityCard } from "@/components/Cards/ActivityCard";
import { WeatherCard } from "@/components/Cards/WeatherCard";
import { PlaceDetailModal } from "@/components/Cards/PlaceDetailModal";
import { ItineraryTimeline } from "@/components/Timeline/ItineraryTimeline";
import { TravelMap } from "@/components/Map/TravelMap";
import { useMapData } from "@/components/Map/use-map-data";
import { ApprovalPanel } from "@/components/Chat/ApprovalPanel";
import { OrchestratorPage } from "@/components/Orchestrator/OrchestratorPage";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Button } from "@/components/ui/Button";
import { Download } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Activity } from "@/types/core";

const tabAnimation = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
  transition: { duration: 0.2 },
};

export function ResultsPage() {
  const { activeTab } = useUiStore();
  const { plan, response } = usePlan();
  const { toggleActivity, selectHotel } = usePlanStore();
  const navigate = useNavigate();
  const [detailActivity, setDetailActivity] = useState<Activity | null>(null);

  useMapData(plan);

  // Derive "Best Value" and "Top Rated" hotel badges
  const hotelBadges = useMemo(() => {
    if (!plan || plan.hotel_options.length === 0) return {};
    const badges: Record<string, { bestValue?: boolean; topRated?: boolean }> =
      {};

    // Best Value = highest score
    const bestValue = [...plan.hotel_options].sort(
      (a, b) => b.score - a.score,
    )[0];
    if (bestValue) {
      badges[bestValue.id] = { ...badges[bestValue.id], bestValue: true };
    }

    // Top Rated = highest reviews_score
    const topRated = [...plan.hotel_options].sort(
      (a, b) => b.reviews_score - a.reviews_score,
    )[0];
    if (topRated && topRated.id !== bestValue?.id) {
      badges[topRated.id] = { ...badges[topRated.id], topRated: true };
    }

    return badges;
  }, [plan]);

  if (!plan || !response) {
    return (
      <GlassPanel className="flex flex-col items-center justify-center gap-4 py-16">
        <p className="text-sm text-slate-400">No plan available yet.</p>
        <Button onClick={() => navigate("/")}>Go to Planner</Button>
      </GlassPanel>
    );
  }

  return (
    <div className="space-y-6">
      {/* Tab navigation for mobile */}
      <div className="flex gap-2 overflow-x-auto lg:hidden">
        {(["plan", "map", "orchestrator"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => useUiStore.getState().setActiveTab(tab)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
              activeTab === tab
                ? "bg-brand-500/20 text-brand-300"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === "plan" && (
          <motion.div key="plan" {...tabAnimation} className="space-y-6">
            <PlanSummaryCard />

            {plan.optimized_itinerary && (
              <ItineraryTimeline
                itinerary={plan.optimized_itinerary}
                activities={plan.activity_options}
              />
            )}

            {/* Hotels */}
            {plan.hotel_options.length > 0 && (
              <section className="space-y-3">
                <h3 className="font-heading text-lg font-semibold text-slate-100">
                  Hotels
                </h3>
                <div className="grid gap-4 md:grid-cols-2">
                  {plan.hotel_options.map((hotel, i) => {
                    const badges = hotelBadges[hotel.id];
                    return (
                      <HotelCard
                        key={hotel.id}
                        hotel={hotel}
                        selected={hotel.id === plan.selected_hotel_id}
                        onSelect={selectHotel}
                        bestValue={badges?.bestValue}
                        topRated={badges?.topRated}
                        index={i}
                      />
                    );
                  })}
                </div>
              </section>
            )}

            {/* Activities */}
            {plan.activity_options.length > 0 && (
              <section className="space-y-3">
                <h3 className="font-heading text-lg font-semibold text-slate-100">
                  Activities
                </h3>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {plan.activity_options.map((activity, i) => (
                    <ActivityCard
                      key={activity.id}
                      activity={activity}
                      selected={plan.selected_activity_ids.includes(
                        activity.id,
                      )}
                      onToggle={toggleActivity}
                      onViewDetails={setDetailActivity}
                      index={i}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Weather Forecast */}
            {plan.destination_analysis?.forecast && (
              <section className="space-y-3">
                <h3 className="font-heading text-lg font-semibold text-slate-100">
                  Weather Forecast
                </h3>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {plan.destination_analysis.forecast.map((f, i) => (
                    <WeatherCard key={f.date} forecast={f} index={i} />
                  ))}
                </div>
              </section>
            )}

            {/* PDF Download */}
            {response.pdf_url && (
              <GlassPanel className="flex items-center justify-between">
                <div>
                  <h4 className="font-heading font-semibold text-slate-200">
                    Itinerary PDF
                  </h4>
                  <p className="text-xs text-slate-500">
                    Download your complete travel plan
                  </p>
                </div>
                <Button
                  variant="secondary"
                  icon={<Download className="h-4 w-4" />}
                  onClick={() => window.open(response.pdf_url, "_blank")}
                >
                  Download
                </Button>
              </GlassPanel>
            )}

            {/* Approval */}
            <ApprovalPanel />
          </motion.div>
        )}

        {activeTab === "map" && (
          <motion.div key="map" {...tabAnimation}>
            <TravelMap />
          </motion.div>
        )}

        {activeTab === "orchestrator" && (
          <motion.div key="orchestrator" {...tabAnimation}>
            <OrchestratorPage />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Place detail modal */}
      <PlaceDetailModal
        activity={detailActivity}
        isOpen={detailActivity !== null}
        onClose={() => setDetailActivity(null)}
        selected={
          detailActivity
            ? plan.selected_activity_ids.includes(detailActivity.id)
            : false
        }
        onToggle={toggleActivity}
      />
    </div>
  );
}
