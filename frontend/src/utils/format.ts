import { format, differenceInCalendarDays, parseISO } from "date-fns";

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

export function formatDateRange(start: string, end: string): string {
  const s = parseISO(start);
  const e = parseISO(end);
  if (s.getFullYear() === e.getFullYear() && s.getMonth() === e.getMonth()) {
    return `${format(s, "MMM d")}–${format(e, "d, yyyy")}`;
  }
  return `${format(s, "MMM d")} – ${format(e, "MMM d, yyyy")}`;
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}min`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}min`;
}

export function formatTemperature(celsius: number): string {
  return `${Math.round(celsius)}°C`;
}

export function computeNights(start: string, end: string): number {
  return differenceInCalendarDays(parseISO(end), parseISO(start));
}
