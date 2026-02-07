import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Star,
  MapPin,
  ChevronLeft,
  ChevronRight,
  Wifi,
  Waves,
  Car,
  Dumbbell,
  Sparkles,
  UtensilsCrossed,
  Wine,
  Snowflake,
  Coffee,
  Shirt,
  ArrowUpDown,
  PawPrint,
  Tv,
  Bath,
  Check,
  Award,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatCurrency } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { HotelOption } from "@/types/core";

interface HotelCardProps {
  hotel: HotelOption;
  selected?: boolean;
  loading?: boolean;
  /** Show "Best Value" badge */
  bestValue?: boolean;
  /** Show "Top Rated" badge */
  topRated?: boolean;
  onSelect?: (id: string) => void;
  /** Index for stagger animation */
  index?: number;
}

const amenityIcons: Record<string, typeof Wifi> = {
  wifi: Wifi,
  "wi-fi": Wifi,
  "free wifi": Wifi,
  internet: Wifi,
  pool: Waves,
  swimming: Waves,
  parking: Car,
  "free parking": Car,
  gym: Dumbbell,
  fitness: Dumbbell,
  spa: Sparkles,
  wellness: Sparkles,
  restaurant: UtensilsCrossed,
  dining: UtensilsCrossed,
  bar: Wine,
  lounge: Wine,
  "air conditioning": Snowflake,
  "a/c": Snowflake,
  breakfast: Coffee,
  "free breakfast": Coffee,
  laundry: Shirt,
  elevator: ArrowUpDown,
  lift: ArrowUpDown,
  "pet friendly": PawPrint,
  pets: PawPrint,
  tv: Tv,
  television: Tv,
  bathtub: Bath,
  jacuzzi: Bath,
};

function getAmenityIcon(amenity: string) {
  const lower = amenity.toLowerCase();
  for (const [key, icon] of Object.entries(amenityIcons)) {
    if (lower.includes(key)) return icon;
  }
  return Check;
}

/** Gradient backgrounds for hotel cards without real photos */
const hotelGradients = [
  "from-blue-900/50 via-indigo-900/30 to-slate-900/50",
  "from-emerald-900/50 via-teal-900/30 to-slate-900/50",
  "from-purple-900/50 via-violet-900/30 to-slate-900/50",
  "from-amber-900/50 via-orange-900/30 to-slate-900/50",
  "from-rose-900/50 via-pink-900/30 to-slate-900/50",
];

function getHotelGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  const idx = Math.abs(hash) % hotelGradients.length;
  return hotelGradients[idx] ?? hotelGradients[0]!;
}

export function HotelCardSkeleton() {
  return (
    <div className="glass-panel overflow-hidden">
      <Skeleton variant="rectangular" className="h-44 w-full" />
      <div className="space-y-3 p-4">
        <Skeleton className="h-5 w-3/4" />
        <div className="flex gap-1">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} variant="circular" className="h-3 w-3" />
          ))}
        </div>
        <Skeleton className="h-4 w-1/2" />
        <div className="flex gap-2">
          <Skeleton variant="rectangular" className="h-7 w-20" />
          <Skeleton variant="rectangular" className="h-7 w-20" />
          <Skeleton variant="rectangular" className="h-7 w-20" />
        </div>
        <Skeleton variant="rectangular" className="h-9 w-full" />
      </div>
    </div>
  );
}

export function HotelCard({
  hotel,
  selected = false,
  loading = false,
  bestValue = false,
  topRated = false,
  onSelect,
  index = 0,
}: HotelCardProps) {
  const [carouselIdx, setCarouselIdx] = useState(0);

  if (loading) return <HotelCardSkeleton />;

  // Generate placeholder "slides" — in production these would be real photo URLs
  const slideCount = Math.min(5, Math.max(3, hotel.stars));
  const gradient = getHotelGradient(hotel.name);

  const topAmenities = hotel.amenities.slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35, ease: "easeOut" }}
    >
      <div
        className={cn(
          "card-hover-lift glass-panel overflow-hidden",
          selected && "ring-2 ring-brand-500/60",
        )}
      >
        {/* Photo carousel area */}
        <div className="relative h-44 overflow-hidden">
          {/* Gradient slide (placeholder for real photos) */}
          <AnimatePresence mode="wait">
            <motion.div
              key={carouselIdx}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className={cn(
                "absolute inset-0 bg-gradient-to-br",
                gradient,
              )}
            >
              {/* Hotel name watermark on slide */}
              <div className="flex h-full items-center justify-center">
                <span className="text-4xl font-bold text-white/[0.06] font-heading">
                  {hotel.name.split(" ").slice(0, 2).join(" ")}
                </span>
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Carousel nav arrows */}
          {slideCount > 1 && (
            <>
              <button
                type="button"
                className="absolute left-2 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white/80 backdrop-blur-sm transition-colors hover:bg-black/60"
                onClick={() =>
                  setCarouselIdx((p) => (p - 1 + slideCount) % slideCount)
                }
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="absolute right-2 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white/80 backdrop-blur-sm transition-colors hover:bg-black/60"
                onClick={() =>
                  setCarouselIdx((p) => (p + 1) % slideCount)
                }
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </>
          )}

          {/* Carousel dots */}
          {slideCount > 1 && (
            <div className="absolute bottom-2 left-1/2 z-10 flex -translate-x-1/2 gap-1.5">
              {Array.from({ length: slideCount }, (_, i) => (
                <button
                  key={i}
                  type="button"
                  className={cn(
                    "h-1.5 rounded-full transition-all",
                    i === carouselIdx
                      ? "w-4 bg-white/80"
                      : "w-1.5 bg-white/30 hover:bg-white/50",
                  )}
                  onClick={() => setCarouselIdx(i)}
                />
              ))}
            </div>
          )}

          {/* Badges overlay */}
          <div className="absolute left-3 top-3 z-10 flex gap-1.5">
            {topRated && (
              <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-2.5 py-1 text-[10px] font-bold text-amber-400 backdrop-blur-sm">
                <Award className="h-3 w-3" />
                Top Rated
              </span>
            )}
            {bestValue && (
              <span className="flex items-center gap-1 rounded-full bg-emerald-500/20 px-2.5 py-1 text-[10px] font-bold text-emerald-400 backdrop-blur-sm">
                <TrendingUp className="h-3 w-3" />
                Best Value
              </span>
            )}
          </div>

          {/* Price overlay */}
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-surface-950/90 to-transparent px-4 pb-3 pt-8">
            <div className="flex items-end justify-between">
              <div>
                <h4 className="font-heading text-base font-semibold text-white line-clamp-1">
                  {hotel.name}
                </h4>
                <div className="mt-0.5 flex items-center gap-1">
                  {Array.from({ length: hotel.stars }, (_, i) => (
                    <Star
                      key={i}
                      className="h-3 w-3 fill-brand-400 text-brand-400"
                    />
                  ))}
                </div>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-xl font-bold text-brand-400">
                  {formatCurrency(hotel.price_per_night, hotel.currency)}
                </p>
                <p className="text-[10px] text-slate-400">per night</p>
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-3 p-4">
          {/* Guest rating */}
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-500/20 text-sm font-bold text-brand-400">
              {hotel.reviews_score.toFixed(1)}
            </span>
            <div>
              <p className="text-xs font-medium text-slate-200">
                {hotel.reviews_score >= 4.5
                  ? "Excellent"
                  : hotel.reviews_score >= 4
                    ? "Very Good"
                    : hotel.reviews_score >= 3.5
                      ? "Good"
                      : "Fair"}
              </p>
              <p className="text-[10px] text-slate-500">Guest rating</p>
            </div>
          </div>

          {/* Location */}
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{hotel.address}</span>
            {hotel.distance_to_center_km > 0 && (
              <span className="shrink-0 text-slate-600">
                · {hotel.distance_to_center_km.toFixed(1)} km
              </span>
            )}
          </div>

          {/* Top 3 amenities with icons */}
          <div className="flex gap-2">
            {topAmenities.map((amenity) => {
              const AmenityIcon = getAmenityIcon(amenity);
              return (
                <div
                  key={amenity}
                  className="flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1.5 text-xs text-slate-300"
                >
                  <AmenityIcon className="h-3.5 w-3.5 text-slate-400" />
                  <span className="truncate">{amenity}</span>
                </div>
              );
            })}
            {hotel.amenities.length > 3 && (
              <div className="flex items-center rounded-lg bg-white/5 px-2.5 py-1.5 text-xs text-slate-500">
                +{hotel.amenities.length - 3}
              </div>
            )}
          </div>

          {/* Select button */}
          {onSelect && (
            <Button
              variant={selected ? "secondary" : "primary"}
              size="sm"
              icon={
                selected ? (
                  <Check className="h-3.5 w-3.5" />
                ) : undefined
              }
              onClick={() => onSelect(hotel.id)}
              className="w-full"
            >
              {selected ? "Selected" : "Select this hotel"}
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
