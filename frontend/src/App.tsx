import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/Layout/AppShell";
import { PlannerPage } from "@/pages/PlannerPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<PlannerPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
