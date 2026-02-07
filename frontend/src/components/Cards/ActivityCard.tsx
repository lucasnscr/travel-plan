import { motion } from "framer-motion";
import {
  Clock,
  MapPin,
  Ticket,
  Home,
  Sun,
  Star,
  Plus,
  Check,
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
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatCurrency, formatDuration } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { Activity } from "@/types/core";

interface ActivityCardProps {
  activity: Activity;
  selected?: boolean;
  loading?: boolean;
  onToggle?: (id: string) => void;
  onViewDetails?: (activity: Activity) => void;
  /** Index for stagger animation delay */
  index?: number;
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

function getPriceLevel(price: number): string {
  if (price === 0) return "Free";
  if (price < 20) return "$";
  if (price < 50) return "$$";
  if (price < 100) return "$$$";
  return "$$$$";
}

function getOpenStatus(hours: Record<string, string>): {
  isOpen: boolean;
  text: string;
} {
  const dayNames = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
  ];
  const now = new Date();
  const today = dayNames[now.getDay()] ?? "monday";
  const todayHours = hours[today];

  if (!todayHours || todayHours.toLowerCase() === "closed") {
    return { isOpen: false, text: "Closed today" };
  }
  return { isOpen: true, text: todayHours };
}

const categoryGradients: Record<string, string> = {
  museum: "from-purple-900/60 to-indigo-900/40",
  restaurant: "from-orange-900/60 to-red-900/40",
  park: "from-green-900/60 to-emerald-900/40",
  temple: "from-amber-900/60 to-yellow-900/40",
  shopping: "from-pink-900/60 to-rose-900/40",
  beach: "from-cyan-900/60 to-blue-900/40",
  nightlife: "from-violet-900/60 to-purple-900/40",
};

function getCategoryGradient(category: string): string {
  const lower = category.toLowerCase();
  for (const [key, gradient] of Object.entries(categoryGradients)) {
    if (lower.includes(key)) return gradient;
  }
  return "from-slate-800/60 to-slate-900/40";
}

export function ActivityCardSkeleton() {
  return (
    <div className="glass-panel overflow-hidden">
      <Skeleton variant="rectangular" className="h-36 w-full" />
      <div className="space-y-2.5 p-4">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-1/3" />
        <div className="flex gap-1">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} variant="circular" className="h-3.5 w-3.5" />
          ))}
        </div>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
        <div className="flex gap-3 pt-1">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
        </div>
        <Skeleton variant="rectangular" className="h-8 w-full" />
      </div>
    </div>
  );
}

export function ActivityCard({
  activity,
  selected = false,
  loading = false,
  onToggle,
  onViewDetails,
  index = 0,
}: ActivityCardProps) {
  if (loading) return <ActivityCardSkeleton />;

  const CategoryIcon = getCategoryIcon(activity.category);
  const priceLevel = getPriceLevel(activity.price);
  const starRating = Math.round(activity.score * 50) / 10; // 0-5 scale
  const openStatus = getOpenStatus(activity.opening_hours);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35, ease: "easeOut" }}
    >
      <div
        className={cn(
          "card-hover-lift glass-panel overflow-hidden",
          selected && "ring-1 ring-brand-500/50",
        )}
      >
        {/* Cover gradient */}
        <button
          type="button"
          className={cn(
            "relative flex h-36 w-full items-end bg-gradient-to-br text-left",
            getCategoryGradient(activity.category),
          )}
          onClick={() => onViewDetails?.(activity)}
        >
          <CategoryIcon className="absolute right-3 top-3 h-8 w-8 text-white/10" />
          <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-surface-950/80 to-transparent" />
          <div className="absolute bottom-3 right-3 z-10">
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-bold",
                priceLevel === "Free"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-brand-500/20 text-brand-400",
              )}
            >
              {priceLevel === "Free"
                ? "Free"
                : `${priceLevel} · ${formatCurrency(activity.price, activity.currency)}`}
            </span>
          </div>
        </button>

        {/* Content */}
        <div className="space-y-2.5 p-4">
          <div>
            <h4 className="font-heading text-sm font-semibold text-slate-100 line-clamp-1">
              {activity.name}
            </h4>
            <div className="mt-1">
              <Badge
                label={activity.category}
                variant="info"
                icon={<CategoryIcon className="h-3 w-3" />}
              />
            </div>
          </div>

          {/* Rating */}
          {starRating > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }, (_, i) => (
                  <Star
                    key={i}
                    className={cn(
                      "h-3.5 w-3.5",
                      i < Math.round(starRating)
                        ? "fill-brand-400 text-brand-400"
                        : "text-slate-700",
                    )}
                  />
                ))}
              </div>
              <span className="text-xs font-medium text-slate-300">
                {starRating.toFixed(1)}
              </span>
            </div>
          )}

          <p className="line-clamp-2 text-xs text-slate-400">
            {activity.description}
          </p>

          {/* Info chips */}
          <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs text-slate-500">
            {Object.keys(activity.opening_hours).length > 0 && (
              <span
                className={cn(
                  "flex items-center gap-1 font-medium",
                  openStatus.isOpen ? "text-emerald-400" : "text-red-400",
                )}
              >
                <Clock className="h-3 w-3" />
                {openStatus.isOpen ? "Open" : "Closed"}
                <span className="font-normal text-slate-500">
                  · {openStatus.text}
                </span>
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDuration(activity.duration_minutes)}
            </span>
            <span className="flex items-center gap-1">
              {activity.indoor ? (
                <>
                  <Home className="h-3 w-3" /> Indoor
                </>
              ) : (
                <>
                  <Sun className="h-3 w-3" /> Outdoor
                </>
              )}
            </span>
            {activity.requires_booking && (
              <span className="flex items-center gap-1 text-amber-400">
                <Ticket className="h-3 w-3" />
                Booking required
              </span>
            )}
          </div>

          {/* Address */}
          <div className="flex items-center gap-1 text-xs text-slate-600">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{activity.address}</span>
          </div>

          {/* Actions */}
          {(onToggle || onViewDetails) && (
            <div className="flex gap-2 pt-1">
              {onToggle && (
                <Button
                  variant={selected ? "secondary" : "primary"}
                  size="sm"
                  icon={
                    selected ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Plus className="h-3.5 w-3.5" />
                    )
                  }
                  onClick={() => onToggle(activity.id)}
                  className="flex-1"
                >
                  {selected ? "Added" : "Add to itinerary"}
                </Button>
              )}
              {onViewDetails && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onViewDetails(activity)}
                >
                  Details
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
