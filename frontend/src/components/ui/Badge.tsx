import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  label: string;
  icon?: ReactNode;
  className?: string;
}

const variants: Record<BadgeVariant, string> = {
  default: "bg-white/10 text-slate-300",
  success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/20",
  danger: "bg-red-500/15 text-red-400 border-red-500/20",
  info: "bg-blue-500/15 text-blue-400 border-blue-500/20",
};

export function Badge({ variant = "default", label, icon, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className,
      )}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {label}
    </span>
  );
}
