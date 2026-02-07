import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Plus, RefreshCw, CheckCircle } from "lucide-react";
import { HotelCard } from "@/components/Cards/HotelCard";
import { ActivityCard } from "@/components/Cards/ActivityCard";
import { WeatherCard } from "@/components/Cards/WeatherCard";
import { Button } from "@/components/ui/Button";
import { usePlanStore } from "@/stores/plan-store";
import { useUiStore } from "@/stores/ui-store";
import type { ChatAttachment } from "@/stores/chat-store";
import type { HotelOption, Activity, WeatherForecast } from "@/types/core";

interface RichResponseProps {
  attachments: ChatAttachment[];
}

export function RichResponse({ attachments }: RichResponseProps) {
  const { toggleActivity, selectHotel } = usePlanStore();
  const plan = usePlanStore((s) => s.response?.plan);
  const navigate = useNavigate();

  return (
    <div className="space-y-3 pt-1">
      {attachments.map((att, i) => {
        switch (att.type) {
          case "hotels":
            return (
              <motion.div
                key={`hotels-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.3 }}
                className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin"
              >
                {(att.data as HotelOption[]).map((hotel) => (
                  <div key={hotel.id} className="w-[280px] shrink-0">
                    <HotelCard
                      hotel={hotel}
                      selected={hotel.id === plan?.selected_hotel_id}
                      onSelect={selectHotel}
                    />
                  </div>
                ))}
              </motion.div>
            );

          case "activities":
            return (
              <motion.div
                key={`activities-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15, duration: 0.3 }}
                className="grid grid-cols-2 gap-2"
              >
                {(att.data as Activity[]).map((activity) => (
                  <ActivityCard
                    key={activity.id}
                    activity={activity}
                    selected={plan?.selected_activity_ids.includes(activity.id)}
                    onToggle={toggleActivity}
                  />
                ))}
              </motion.div>
            );

          case "weather":
            return (
              <motion.div
                key={`weather-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.3 }}
                className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin"
              >
                {(att.data as WeatherForecast[]).map((f) => (
                  <div key={f.date} className="w-[160px] shrink-0">
                    <WeatherCard forecast={f} />
                  </div>
                ))}
              </motion.div>
            );

          case "actions":
            return (
              <motion.div
                key={`actions-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25, duration: 0.3 }}
                className="flex flex-wrap gap-2"
              >
                {(att.data as string[]).map((action) => {
                  const config = getActionConfig(action);
                  return (
                    <Button
                      key={action}
                      variant="ghost"
                      size="sm"
                      icon={config.icon}
                      onClick={() => {
                        if (action === "View alternatives") {
                          useUiStore.getState().setActiveTab("plan");
                          navigate("/results");
                        } else if (action === "Confirm plan") {
                          navigate("/results");
                        }
                      }}
                      className="border border-white/10 text-xs"
                    >
                      {action}
                    </Button>
                  );
                })}
              </motion.div>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}

function getActionConfig(action: string) {
  switch (action) {
    case "Add to itinerary":
      return { icon: <Plus className="h-3 w-3" /> };
    case "View alternatives":
      return { icon: <RefreshCw className="h-3 w-3" /> };
    case "Confirm plan":
      return { icon: <CheckCircle className="h-3 w-3" /> };
    default:
      return { icon: null };
  }
}
