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
  personal_relevance: number;
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

// ---- Topics ----

export interface Topic {
  id: string;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  priority: string;
  enabled: boolean;
}

export type TopicInput = {
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  priority?: string;
  enabled?: boolean;
};

export function fetchTopics(): Promise<Topic[]> {
  return getJSON<Topic[]>("/topics");
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const createTopic = (t: TopicInput) => send<Topic>("/topics", "POST", t);
export const updateTopic = (id: string, t: Partial<TopicInput>) =>
  send<Topic>(`/topics/${id}`, "PATCH", t);
export const deleteTopic = (id: string) => send<void>(`/topics/${id}`, "DELETE");

// ---- Content candidates ----

export interface Candidate {
  id: string;
  event_id: string;
  text: string;
  angle: string;
  platform: string;
  trend_score: number;
  personal_score: number;
  viral_score: number;
  novelty_score: number;
  risk_score: number;
  rank: number;
}

export const generateCandidates = (eventId: string) =>
  send<Candidate[]>(`/events/${eventId}/generate`, "POST");
export const fetchCandidates = (eventId: string) =>
  getJSON<Candidate[]>(`/events/${eventId}/candidates`);

// ---- Recommended action (PROJECT.md §31) ----

export function recommendedAction(opportunity: number): { label: string; tone: string } {
  if (opportunity >= 85) return { label: "POST NOW", tone: "hot" };
  if (opportunity >= 70) return { label: "POST WITHIN 30 MIN", tone: "good" };
  if (opportunity >= 50) return { label: "CONSIDER", tone: "warn" };
  return { label: "WAIT", tone: "muted" };
}
