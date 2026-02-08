import { get, post, patch, postForm } from "./api-client";
import type {
  PlanRequest,
  PlanResponse,
  ApprovalResponse,
  HealthResponse,
} from "@/types/api";

export async function planTrip(req: PlanRequest): Promise<PlanResponse> {
  // Use FormData only when file uploads are present
  const hasFiles = req.audio_file || req.image_file || req.pdf_file;

  if (hasFiles) {
    const fd = new FormData();
    fd.append("destination", req.destination);
    fd.append("start_date", req.start_date);
    fd.append("end_date", req.end_date);
    fd.append("budget", String(req.budget));
    fd.append("currency", req.currency);
    fd.append("group_size", String(req.group_size));
    fd.append("interests", req.interests);
    if (req.audio_file) fd.append("audio_file", req.audio_file);
    if (req.image_file) fd.append("image_file", req.image_file);
    if (req.pdf_file) fd.append("pdf_file", req.pdf_file);
    return postForm<PlanResponse>("/api/plan/form", fd);
  }

  // JSON body for text-only requests
  return post<PlanResponse>("/api/plan", {
    destination: req.destination,
    start_date: req.start_date,
    end_date: req.end_date,
    budget: Number(req.budget),
    currency: req.currency,
    num_travelers: Number(req.group_size),
    preferences: req.interests
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  });
}

export async function approvePlan(
  decision: "approved" | "rejected",
  feedback = "",
): Promise<ApprovalResponse> {
  const fd = new FormData();
  fd.append("decision", decision);
  fd.append("feedback", feedback);
  return postForm<ApprovalResponse>("/api/approve", fd);
}

export async function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("/health");
}

export function getMapUrl(filename: string): string {
  return `/api/map/${filename}`;
}

export function getPdfUrl(filename: string): string {
  return `/api/pdf/${filename}`;
}

// ---------------------------------------------------------------------------
// Trip CRUD (new endpoints)
// ---------------------------------------------------------------------------

export interface TripPlanResponse {
  plan_id: string;
  destination: string;
  start_date: string;
  end_date: string;
  days: unknown[];
  hotels: unknown[];
  activities: unknown[];
  total_cost: number;
  currency: string;
  weather_summary: unknown | null;
  approval_status: string;
  map_url: string;
  pdf_url: string;
}

export async function getTrip(tripId: string): Promise<TripPlanResponse> {
  return get<TripPlanResponse>(`/api/trip/${tripId}`);
}

export async function updateItinerary(
  tripId: string,
  days: unknown[],
): Promise<TripPlanResponse> {
  return patch<TripPlanResponse>(`/api/trip/${tripId}/itinerary`, { days });
}

export async function approveTrip(
  tripId: string,
  decision: "approved" | "rejected",
  feedback = "",
): Promise<ApprovalResponse> {
  return post<ApprovalResponse>(`/api/trip/${tripId}/approve`, {
    decision,
    feedback,
  });
}
