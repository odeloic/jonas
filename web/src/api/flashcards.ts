import { apiFetch } from "./client";
import type { FlashcardSetSummary, FlashcardSetDetail } from "./types";

export function fetchFlashcardSets(): Promise<FlashcardSetSummary[]> {
  return apiFetch<FlashcardSetSummary[]>("/api/flashcards");
}

export function fetchFlashcardSet(id: number): Promise<FlashcardSetDetail> {
  return apiFetch<FlashcardSetDetail>(`/api/flashcards/${id}`);
}
