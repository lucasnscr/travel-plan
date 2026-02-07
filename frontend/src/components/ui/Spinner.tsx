import { cn } from "@/utils/cn";

type SpinnerSize = "sm" | "md" | "lg";

const sizes: Record<SpinnerSize, string> = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-3",
};

export function Spinner({ size = "md", className }: { size?: SpinnerSize; className?: string }) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-brand-500 border-t-transparent",
        sizes[size],
        className,
      )}
    />
  );
}
