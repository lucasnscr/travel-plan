import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { AppShell } from "@/components/Layout/AppShell";
import { PlannerPage } from "@/pages/PlannerPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { ToastContainer } from "@/components/ui/Toast";
import { Spinner } from "@/components/ui/Spinner";
import { DemoOverlay } from "@/components/Demo/DemoOverlay";
import { useDemoStore } from "@/stores/demo-store";
import { useUiStore } from "@/stores/ui-store";

const ResultsPage = lazy(() =>
  import("@/pages/ResultsPage").then((m) => ({ default: m.ResultsPage })),
);
const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);

function PageFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <Spinner size="lg" />
    </div>
  );
}

/** Keyboard shortcuts for demo mode — must be inside BrowserRouter */
function DemoKeyboardHandler() {
  const navigate = useNavigate();
  const { isDemoMode, toggleDemo, toggleHighlight, resetDemo, jumpToDay, playDemo } =
    useDemoStore();
  const { setActiveTab } = useUiStore();

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      // Skip if user is typing in an input
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const key = e.key.toLowerCase();

      switch (key) {
        case "d":
          e.preventDefault();
          toggleDemo();
          break;

        case "h":
          if (isDemoMode) {
            e.preventDefault();
            toggleHighlight();
          }
          break;

        case "r":
          if (isDemoMode) {
            e.preventDefault();
            resetDemo(navigate);
          }
          break;

        case "o":
          if (isDemoMode) {
            e.preventDefault();
            setActiveTab("orchestrator");
          }
          break;

        case "f":
          if (isDemoMode) {
            e.preventDefault();
            // Click the fullscreen button on the map if visible
            const btn = document.querySelector<HTMLButtonElement>(
              '[aria-label="Fullscreen map"], [aria-label="Exit fullscreen"]',
            );
            btn?.click();
          }
          break;

        case "escape":
          if (isDemoMode) {
            e.preventDefault();
            toggleDemo();
          }
          break;

        case " ":
          if (isDemoMode) {
            e.preventDefault();
            const state = useDemoStore.getState();
            if (state.isPlaying) {
              state.stopDemo();
            } else {
              playDemo(navigate);
            }
          }
          break;

        default:
          // Number keys 1-5 for day jumping
          if (isDemoMode && key >= "1" && key <= "5") {
            e.preventDefault();
            setActiveTab("map");
            jumpToDay(parseInt(key, 10));
          }
          break;
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isDemoMode, toggleDemo, toggleHighlight, resetDemo, jumpToDay, playDemo, setActiveTab, navigate]);

  return <DemoOverlay />;
}

export function App() {
  return (
    <ErrorBoundary section="Application">
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<PlannerPage />} />
              <Route path="results" element={<ResultsPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
        <DemoKeyboardHandler />
        <ToastContainer />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
