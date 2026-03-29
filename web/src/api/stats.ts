import { apiFetch } from "./client";
import type { Stats } from "./types";

export function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/api/stats");
}
