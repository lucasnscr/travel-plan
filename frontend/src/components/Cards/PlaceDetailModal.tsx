import { useState, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Star,
  Clock,
  MapPin,
  Ticket,
  Home,
  Sun,
  ExternalLink,
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
  Navigation,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatCurrency, formatDuration } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { Activity } from "@/types/core";

interface PlaceDetailModalProps {
  activity: Activity | null;
  isOpen: boolean;
  onClose: () => void;
  /** Whether this activity is selected in the itinerary */
  selected?: boolean;
  /** Toggle selection */
  onToggle?: (id: string) => void;
}

const categoryIcons: Record<string, typeof Landmark> = {
  museum: Landmark,
  restaurant: UtensilsCrossed,
  food: UtensilsCrossed,
  dining: UtensilsCrossed,
  park: TreePine,
  garden: TreePine,
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
  sightseeing: Camera,
};

function getCategoryIcon(category: string) {
  const lower = category.toLowerCase();
  for (const [key, icon] of Object.entries(categoryIcons)) {
    if (lower.includes(key)) return icon;
  }
  return MapPin;
}

const categoryGradients: Record<string, string> = {
  museum: "from-purple-900/80 via-indigo-900/50 to-surface-950",
  restaurant: "from-orange-900/80 via-red-900/50 to-surface-950",
  park: "from-green-900/80 via-emerald-900/50 to-surface-950",
  temple: "from-amber-900/80 via-yellow-900/50 to-surface-950",
  shopping: "from-pink-900/80 via-rose-900/50 to-surface-950",
  beach: "from-cyan-900/80 via-blue-900/50 to-surface-950",
  nightlife: "from-violet-900/80 via-purple-900/50 to-surface-950",
};

function getCategoryGradient(category: string): string {
  const lower = category.toLowerCase();
  for (const [key, gradient] of Object.entries(categoryGradients)) {
    if (lower.includes(key)) return gradient;
  }
  return "from-slate-800/80 via-slate-900/50 to-surface-950";
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
    "sunday", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday",
  ];
  const now = new Date();
  const today = dayNames[now.getDay()] ?? "monday";
  const todayHours = hours[today];
  if (!todayHours || todayHours.toLowerCase() === "closed") {
    return { isOpen: false, text: "Closed today" };
  }
  return { isOpen: true, text: todayHours };
}

/** Generate day labels for the opening hours table */
const DAY_LABELS: Record<string, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

const DAY_ORDER = [
  "monday", "tuesday", "wednesday", "thursday",
  "friday", "saturday", "sunday",
];

export function PlaceDetailModal({
  activity,
  isOpen,
  onClose,
  selected = false,
  onToggle,
}: PlaceDetailModalProps) {
  const [galleryIdx, setGalleryIdx] = useState(0);

  // Reset gallery index on open
  useEffect(() => {
    if (isOpen) setGalleryIdx(0);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Keyboard navigation for gallery
  const handleKeyNav = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") setGalleryIdx((p) => Math.max(0, p - 1));
      if (e.key === "ArrowRight") setGalleryIdx((p) => Math.min(2, p + 1));
    },
    [],
  );

  useEffect(() => {
    if (!isOpen) return;
    window.addEventListener("keydown", handleKeyNav);
    return () => window.removeEventListener("keydown", handleKeyNav);
  }, [isOpen, handleKeyNav]);

  if (!activity) return null;

  const CategoryIcon = getCategoryIcon(activity.category);
  const gradient = getCategoryGradient(activity.category);
  const starRating = Math.round(activity.score * 50) / 10;
  const priceLevel = getPriceLevel(activity.price);
  const openStatus = getOpenStatus(activity.opening_hours);
  const slideCount = 3; // placeholder gallery slides

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-surface-950/80 backdrop-blur-md"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          {/* Modal content */}
          <motion.div
            className="relative z-10 mx-4 my-8 w-full max-w-2xl"
            initial={{ opacity: 0, y: 40, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.98 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <div className="glass-panel overflow-hidden">
              {/* Close button */}
              <button
                type="button"
                onClick={onClose}
                className="absolute right-4 top-4 z-20 flex h-8 w-8 items-center justify-center rounded-full bg-black/40 text-white/70 backdrop-blur-sm transition-colors hover:bg-black/60 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>

              {/* Photo gallery */}
              <div className="relative h-56 overflow-hidden sm:h-72">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={galleryIdx}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className={cn(
                      "absolute inset-0 bg-gradient-to-br",
                      gradient,
                    )}
                  >
                    <div className="flex h-full items-center justify-center">
                      <CategoryIcon className="h-20 w-20 text-white/[0.06]" />
                    </div>
                  </motion.div>
                </AnimatePresence>

                {/* Gallery nav */}
                {slideCount > 1 && (
                  <>
                    <button
                      type="button"
                      className="absolute left-3 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white/80 backdrop-blur-sm transition-colors hover:bg-black/60"
                      onClick={() =>
                        setGalleryIdx((p) =>
                          (p - 1 + slideCount) % slideCount,
                        )
                      }
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      className="absolute right-12 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white/80 backdrop-blur-sm transition-colors hover:bg-black/60"
                      onClick={() =>
                        setGalleryIdx((p) => (p + 1) % slideCount)
                      }
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </>
                )}

                {/* Gallery dots */}
                <div className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 gap-1.5">
                  {Array.from({ length: slideCount }, (_, i) => (
                    <button
                      key={i}
                      type="button"
                      className={cn(
                        "h-1.5 rounded-full transition-all",
                        i === galleryIdx
                          ? "w-5 bg-white/80"
                          : "w-1.5 bg-white/30 hover:bg-white/50",
                      )}
                      onClick={() => setGalleryIdx(i)}
                    />
                  ))}
                </div>

                {/* Price overlay */}
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-surface-950/90 to-transparent px-6 pb-4 pt-10">
                  <Badge
                    label={activity.category}
                    variant="info"
                    icon={<CategoryIcon className="h-3 w-3" />}
                  />
                </div>
              </div>

              {/* Body */}
              <div className="space-y-5 p-6">
                {/* Header */}
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-heading text-xl font-bold text-slate-100">
                      {activity.name}
                    </h2>

                    {/* Stars */}
                    {starRating > 0 && (
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <div className="flex items-center gap-0.5">
                          {Array.from({ length: 5 }, (_, i) => (
                            <Star
                              key={i}
                              className={cn(
                                "h-4 w-4",
                                i < Math.round(starRating)
                                  ? "fill-brand-400 text-brand-400"
                                  : "text-slate-700",
                              )}
                            />
                          ))}
                        </div>
                        <span className="text-sm font-medium text-slate-300">
                          {starRating.toFixed(1)}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Price */}
                  <div className="shrink-0 text-right">
                    {activity.price > 0 ? (
                      <>
                        <p className="text-xl font-bold text-brand-400">
                          {formatCurrency(activity.price, activity.currency)}
                        </p>
                        <p className="text-xs text-slate-500">{priceLevel}</p>
                      </>
                    ) : (
                      <Badge label="Free" variant="success" />
                    )}
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm leading-relaxed text-slate-400">
                  {activity.description}
                </p>

                {/* Info grid */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {/* Duration */}
                  <div className="rounded-lg bg-white/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Clock className="h-3.5 w-3.5" />
                      Duration
                    </div>
                    <p className="mt-1 text-sm font-medium text-slate-200">
                      {formatDuration(activity.duration_minutes)}
                    </p>
                  </div>

                  {/* Open/Closed */}
                  <div className="rounded-lg bg-white/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Clock className="h-3.5 w-3.5" />
                      Status
                    </div>
                    <p
                      className={cn(
                        "mt-1 text-sm font-medium",
                        openStatus.isOpen
                          ? "text-emerald-400"
                          : "text-red-400",
                      )}
                    >
                      {openStatus.isOpen ? "Open" : "Closed"}
                    </p>
                  </div>

                  {/* Indoor/Outdoor */}
                  <div className="rounded-lg bg-white/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      {activity.indoor ? (
                        <Home className="h-3.5 w-3.5" />
                      ) : (
                        <Sun className="h-3.5 w-3.5" />
                      )}
                      Type
                    </div>
                    <p className="mt-1 text-sm font-medium text-slate-200">
                      {activity.indoor ? "Indoor" : "Outdoor"}
                    </p>
                  </div>

                  {/* Booking */}
                  <div className="rounded-lg bg-white/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Ticket className="h-3.5 w-3.5" />
                      Booking
                    </div>
                    <p
                      className={cn(
                        "mt-1 text-sm font-medium",
                        activity.requires_booking
                          ? "text-amber-400"
                          : "text-slate-200",
                      )}
                    >
                      {activity.requires_booking ? "Required" : "Not needed"}
                    </p>
                  </div>
                </div>

                {/* Opening hours table */}
                {Object.keys(activity.opening_hours).length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium uppercase tracking-wider text-slate-500">
                      Opening Hours
                    </h3>
                    <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
                      {DAY_ORDER.map((day) => {
                        const hours = activity.opening_hours[day];
                        const label = DAY_LABELS[day] ?? day;
                        return (
                          <div
                            key={day}
                            className="flex justify-between text-xs"
                          >
                            <span className="font-medium text-slate-400">
                              {label}
                            </span>
                            <span
                              className={cn(
                                hours &&
                                  hours.toLowerCase() !== "closed"
                                  ? "text-slate-300"
                                  : "text-red-400/70",
                              )}
                            >
                              {hours ?? "—"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Mini map */}
                <div>
                  <h3 className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Location
                  </h3>
                  <div className="mt-2 overflow-hidden rounded-lg border border-white/10">
                    <div className="relative flex h-36 items-center justify-center bg-surface-900">
                      {/* Stylized pin on dark background */}
                      <div className="flex flex-col items-center gap-2">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500/20">
                          <Navigation className="h-5 w-5 text-brand-400" />
                        </div>
                        <p className="text-xs text-slate-400">
                          {activity.coordinates.lat.toFixed(4)},{" "}
                          {activity.coordinates.lng.toFixed(4)}
                        </p>
                      </div>

                      {/* Grid pattern background */}
                      <div
                        className="absolute inset-0 opacity-[0.03]"
                        style={{
                          backgroundImage:
                            "radial-gradient(circle, #fff 1px, transparent 1px)",
                          backgroundSize: "20px 20px",
                        }}
                      />
                    </div>
                    <div className="flex items-center gap-2 bg-white/[0.03] px-3 py-2">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                      <p className="text-xs text-slate-400 line-clamp-1">
                        {activity.address}
                      </p>
                      <a
                        href={`https://www.google.com/maps/search/?api=1&query=${activity.coordinates.lat},${activity.coordinates.lng}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-auto shrink-0 text-xs text-brand-400 hover:text-brand-300"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </div>
                  </div>
                </div>

                {/* Source */}
                {activity.data_source && (
                  <p className="text-[10px] text-slate-600">
                    Data source: {activity.data_source}
                  </p>
                )}

                {/* Actions */}
                <div className="flex gap-3 border-t border-white/5 pt-4">
                  {onToggle && (
                    <Button
                      variant={selected ? "secondary" : "primary"}
                      icon={
                        selected ? (
                          <Check className="h-4 w-4" />
                        ) : (
                          <Plus className="h-4 w-4" />
                        )
                      }
                      onClick={() => onToggle(activity.id)}
                      className="flex-1"
                    >
                      {selected ? "Added to itinerary" : "Add to itinerary"}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    onClick={onClose}
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
