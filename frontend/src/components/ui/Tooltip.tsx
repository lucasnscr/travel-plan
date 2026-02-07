import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/utils/cn";

interface TooltipProps {
  content: string;
  position?: "top" | "bottom";
  children: ReactNode;
  className?: string;
}

export function Tooltip({
  content,
  position = "top",
  children,
  className,
}: TooltipProps) {
  const [show, setShow] = useState(false);

  return (
    <div
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      <AnimatePresence>
        {show && (
          <motion.div
            initial={{ opacity: 0, y: position === "top" ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs",
              "glass-panel-sm text-slate-200 shadow-xl",
              position === "top" ? "bottom-full mb-2" : "top-full mt-2",
            )}
          >
            {content}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
