import { usePlanStore } from "@/stores/plan-store";
import { computeNights } from "@/utils/format";

export function usePlan() {
  const { request, response, isPlanning, error, submitPlan, approve, reject, clearPlan, toggleActivity, selectHotel } =
    usePlanStore();

  const plan = response?.plan ?? null;

  const tripNights =
    plan?.dates?.start_date && plan?.dates?.end_date
      ? computeNights(plan.dates.start_date, plan.dates.end_date)
      : 0;

  const selectedHotel = plan?.hotel_options?.find(
    (h) => h.id === plan.selected_hotel_id,
  );

  const budgetTotal = plan?.budget?.total ?? 0;
  const currentCost = plan?.current_cost ?? 0;
  const budgetRemaining = budgetTotal - currentCost;
  const budgetStatus: "ok" | "warning" | "over" =
    budgetRemaining < 0 ? "over" : budgetRemaining < budgetTotal * 0.1 ? "warning" : "ok";

  return {
    request,
    response,
    plan,
    isPlanning,
    error,
    tripNights,
    selectedHotel,
    budgetTotal,
    currentCost,
    budgetRemaining,
    budgetStatus,
    submitPlan,
    approve,
    reject,
    clearPlan,
    toggleActivity,
    selectHotel,
  };
}
