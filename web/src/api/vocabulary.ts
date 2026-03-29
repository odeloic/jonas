import { apiFetch } from "./client";
import type { VocabItem } from "./types";

export function fetchVocabulary(params?: {
  q?: string;
  word_class?: string;
}): Promise<VocabItem[]> {
  const sp = new URLSearchParams();
  if (params?.q) sp.set("q", params.q);
  if (params?.word_class) sp.set("word_class", params.word_class);
  const qs = sp.toString();
  return apiFetch<VocabItem[]>(`/api/vocabulary${qs ? `?${qs}` : ""}`);
}

export function fetchWordClasses(): Promise<string[]> {
  return apiFetch<string[]>("/api/vocabulary/word-classes");
}
