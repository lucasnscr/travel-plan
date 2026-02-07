import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapIcon,
  FileText,
  LayoutDashboard,
  ClipboardCheck,
  Workflow,
  Compass,
} from "lucide-react";
import { useUiStore } from "@/stores/ui-store";
import { useIsMobile } from "@/hooks/use-media-query";
import { cn } from "@/utils/cn";

const navItems = [
  { label: "Planner", icon: Compass, path: "/" },
  { label: "Results", icon: ClipboardCheck, path: "/results" },
  { label: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
] as const;

const resultTabs = [
  { label: "Plan", icon: FileText, tab: "plan" as const },
  { label: "Map", icon: MapIcon, tab: "map" as const },
  { label: "Orchestrator", icon: Workflow, tab: "orchestrator" as const },
] as const;

export function Sidebar() {
  const { sidebarOpen, setSidebarOpen, activeTab, setActiveTab } = useUiStore();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const location = useLocation();

  const isOpen = isMobile ? sidebarOpen : true;

  return (
    <>
      {/* Mobile backdrop */}
      <AnimatePresence>
        {isMobile && sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <motion.aside
            initial={isMobile ? { x: -280 } : false}
            animate={{ x: 0 }}
            exit={isMobile ? { x: -280 } : undefined}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className={cn(
              "z-30 flex w-56 shrink-0 flex-col gap-1 border-r border-white/5 bg-surface-950/80 p-3 backdrop-blur-xl",
              isMobile ? "fixed inset-y-0 left-0 pt-16" : "relative",
            )}
          >
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
              Navigation
            </p>
            {navItems.map((item) => {
              const active = location.pathname === item.path;
              return (
                <button
                  key={item.path}
                  onClick={() => {
                    navigate(item.path);
                    if (isMobile) setSidebarOpen(false);
                  }}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-brand-500/15 text-brand-400"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}

            {location.pathname === "/results" && (
              <>
                <p className="mb-1 mt-4 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
                  Results View
                </p>
                {resultTabs.map((item) => {
                  const active = activeTab === item.tab;
                  return (
                    <button
                      key={item.tab}
                      onClick={() => setActiveTab(item.tab)}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-white/10 text-slate-100"
                          : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </>
            )}
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
