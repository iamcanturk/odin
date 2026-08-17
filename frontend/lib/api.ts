// Typed client for the ODIN v1 API.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type EventStatus =
  | "discovered"
  | "verified"
  | "rising"
  | "trending"
  | "saturated"
  | "declining"
  | "archived";

export interface EventSummary {
  id: string;
  title: string;
  summary: string | null;
  status: EventStatus;
  trend_score: number;
  opportunity_score: number;
  confidence_score: number;
  first_seen_at: string;
  last_seen_at: string;
  source_count: number;
  item_count: number;
}

export interface EventList {
  total: number;
  items: EventSummary[];
}

export interface EventSourceRef {
  id: string;
  name: string;
  type: string;
  confidence: number;
}

export interface EventItem {
  id: string;
  title: string | null;
  url: string | null;
  source_name: string | null;
  published_at: string | null;
}

export interface EventDetail extends EventSummary {
  entities: string[];
  velocity: Record<string, number>;
  scoring_version: string | null;
  sources: EventSourceRef[];
  items: EventItem[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchEvents(params?: {
  limit?: number;
  status?: string;
  orderBy?: string;
}): Promise<EventList> {
  const qs = new URLSearchParams();
  qs.set("limit", String(params?.limit ?? 50));
  if (params?.status) qs.set("status", params.status);
  if (params?.orderBy) qs.set("order_by", params.orderBy);
  return getJSON<EventList>(`/events?${qs.toString()}`);
}

export function fetchEvent(id: string): Promise<EventDetail> {
  return getJSON<EventDetail>(`/events/${id}`);
}
