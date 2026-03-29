import { apiFetch } from "./client";
import type {
  AssignmentSummary,
  AssignmentDetail,
  SubmissionAnswers,
  SubmissionResult,
} from "./types";

export function fetchAssignments(): Promise<AssignmentSummary[]> {
  return apiFetch<AssignmentSummary[]>("/api/assignments");
}

export function fetchAssignment(id: number): Promise<AssignmentDetail> {
  return apiFetch<AssignmentDetail>(`/api/assignments/${id}`);
}

export function submitAssignment(
  id: number,
  answers: SubmissionAnswers,
): Promise<SubmissionResult> {
  return apiFetch<SubmissionResult>(`/api/assignments/${id}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function fetchSubmission(
  assignmentId: number,
  submissionId: number,
): Promise<SubmissionResult> {
  return apiFetch<SubmissionResult>(
    `/api/assignments/${assignmentId}/results/${submissionId}`,
  );
}
