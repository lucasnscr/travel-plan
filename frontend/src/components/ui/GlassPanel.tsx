import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/utils/cn";

interface GlassPanelProps extends HTMLMotionProps<"div"> {
  hover?: boolean;
  padding?: "none" | "sm" | "md" | "lg";
}

const paddings = {
  none: "",
  sm: "p-3",
  md: "p-5",
  lg: "p-7",
};

export function GlassPanel({
  children,
  className,
  hover = false,
  padding = "md",
  ...rest
}: GlassPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "glass-panel",
        paddings[padding],
        hover && "transition-colors hover:bg-white/[0.08]",
        className,
      )}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
