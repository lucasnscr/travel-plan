import { cn } from "@/utils/cn";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
  width?: string | number;
  height?: string | number;
}

export function Skeleton({
  className,
  variant = "text",
  width,
  height,
}: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-skeleton-shimmer bg-gradient-to-r from-white/[0.06] via-white/[0.12] to-white/[0.06] bg-[length:200%_100%]",
        variant === "text" && "h-4 rounded",
        variant === "circular" && "rounded-full",
        variant === "rectangular" && "rounded-lg",
        className,
      )}
      style={{ width, height }}
    />
  );
}
