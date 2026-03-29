import { apiFetch } from "./client";
import type { GrammarRule, TopicSummary } from "./types";

export function fetchGrammarRules(params?: {
  topic?: string;
  q?: string;
}): Promise<GrammarRule[]> {
  const sp = new URLSearchParams();
  if (params?.topic) sp.set("topic", params.topic);
  if (params?.q) sp.set("q", params.q);
  const qs = sp.toString();
  return apiFetch<GrammarRule[]>(`/api/grammar${qs ? `?${qs}` : ""}`);
}

export function fetchTopics(): Promise<TopicSummary[]> {
  return apiFetch<TopicSummary[]>("/api/grammar/topics");
}
