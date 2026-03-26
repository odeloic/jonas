import { apiFetch } from "./client";
import type { AssignmentSummary, AssignmentDetail } from "./types";

export function fetchAssignments(): Promise<AssignmentSummary[]> {
  return apiFetch<AssignmentSummary[]>("/api/assignments");
}

export function fetchAssignment(id: number): Promise<AssignmentDetail> {
  return apiFetch<AssignmentDetail>(`/api/assignments/${id}`);
}
