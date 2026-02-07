import type { OrchestratorNode } from "@/types/api";

/** Ordered list of graph nodes matching planner_graph.py */
export const GRAPH_NODES: OrchestratorNode[] = [
  "gather_requirements",
  "analyze_destination",
  "search_flights",
  "search_hotels",
  "search_activities",
  "optimize_itinerary",
  "calculate_budget",
  "risk_and_policy_check",
  "present_for_approval",
  "process_feedback",
  "book_services",
  "generate_documents",
];

/** DAG edges (from → to) */
export const GRAPH_EDGES: [OrchestratorNode, OrchestratorNode][] = [
  ["gather_requirements", "analyze_destination"],
  ["analyze_destination", "search_flights"],
  ["search_flights", "search_hotels"],
  ["search_hotels", "search_activities"],
  ["search_activities", "optimize_itinerary"],
  ["optimize_itinerary", "calculate_budget"],
  ["calculate_budget", "risk_and_policy_check"],
  ["calculate_budget", "search_flights"], // budget loop
  ["risk_and_policy_check", "present_for_approval"],
  ["present_for_approval", "book_services"],
  ["present_for_approval", "process_feedback"], // rejection
  ["process_feedback", "search_flights"],
  ["process_feedback", "search_hotels"],
  ["process_feedback", "search_activities"],
  ["book_services", "generate_documents"],
];

/** Human-readable labels for each node */
export const NODE_LABELS: Record<OrchestratorNode, string> = {
  gather_requirements: "Requirements",
  analyze_destination: "Destination Analysis",
  search_flights: "Flights",
  search_hotels: "Hotels",
  search_activities: "Activities",
  optimize_itinerary: "Itinerary",
  calculate_budget: "Budget",
  risk_and_policy_check: "Risk Check",
  present_for_approval: "Approval",
  process_feedback: "Feedback",
  book_services: "Booking",
  generate_documents: "Documents",
};

/** Descriptions for each node */
export const NODE_DESCRIPTIONS: Record<OrchestratorNode, string> = {
  gather_requirements: "Collecting trip preferences and constraints",
  analyze_destination: "Weather, events, and destination intelligence",
  search_flights: "Searching for optimal flight options",
  search_hotels: "Finding hotels matching your criteria",
  search_activities: "Discovering activities and experiences",
  optimize_itinerary: "Building day-by-day schedule",
  calculate_budget: "Computing total costs and budget fit",
  risk_and_policy_check: "Validating safety and policy compliance",
  present_for_approval: "Awaiting your review and approval",
  process_feedback: "Incorporating your feedback",
  book_services: "Processing bookings and reservations",
  generate_documents: "Creating itinerary PDF and calendar",
};

/** The main linear path (for progress bar, excludes branching nodes) */
export const LINEAR_PATH: OrchestratorNode[] = [
  "gather_requirements",
  "analyze_destination",
  "search_flights",
  "search_hotels",
  "search_activities",
  "optimize_itinerary",
  "calculate_budget",
  "risk_and_policy_check",
  "present_for_approval",
  "book_services",
  "generate_documents",
];

export const SUPPORTED_CURRENCIES = [
  "USD", "EUR", "GBP", "BRL", "JPY", "AUD", "CAD", "CHF",
] as const;

export const INTEREST_PRESETS = [
  { label: "Museums", value: "museums" },
  { label: "Gastronomy", value: "gastronomy" },
  { label: "Outdoors", value: "outdoors" },
  { label: "Nightlife", value: "nightlife" },
  { label: "Shopping", value: "shopping" },
  { label: "Culture", value: "culture" },
  { label: "Adventure", value: "adventure" },
  { label: "Wellness", value: "wellness" },
  { label: "Photography", value: "photography" },
  { label: "History", value: "history" },
] as const;
