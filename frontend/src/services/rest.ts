import { get, postForm } from "./api-client";
import type {
  PlanRequest,
  PlanResponse,
  ApprovalResponse,
  HealthResponse,
} from "@/types/api";

export async function planTrip(req: PlanRequest): Promise<PlanResponse> {
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

  return postForm<PlanResponse>("/api/plan", fd);
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
