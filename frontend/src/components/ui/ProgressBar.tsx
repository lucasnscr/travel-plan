import { motion } from "framer-motion";
import { cn } from "@/utils/cn";

interface ProgressBarProps {
  value: number;
  label?: string;
  variant?: "default" | "success" | "warning";
  className?: string;
}

const barColors = {
  default: "from-brand-500 to-brand-400",
  success: "from-emerald-500 to-emerald-400",
  warning: "from-amber-500 to-amber-400",
};

export function ProgressBar({
  value,
  label,
  variant = "default",
  className,
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">{label}</span>
          <span className="font-medium text-slate-300">{Math.round(clamped)}%</span>
        </div>
      )}
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className={cn("h-full rounded-full bg-gradient-to-r", barColors[variant])}
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
