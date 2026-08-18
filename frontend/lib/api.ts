// Typed client for the ODIN v1 API.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// ---- Auth token (localStorage) ----

const TOKEN_KEY = "odin_token";

export function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
}
export function setToken(token: string): void {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function handleUnauthorized(path: string): void {
  // Don't bounce on auth calls themselves (e.g. a failed login).
  if (path.startsWith("/auth")) return;
  clearToken();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    // Full reload on 401 to fully reset client state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }
}

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
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (res.status === 401) handleUnauthorized(path);
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
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...authHeaders(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) handleUnauthorized(path);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

// ---- Auth ----

export interface AuthConfig {
  auth_required: boolean;
}

export const fetchAuthConfig = () => getJSON<AuthConfig>("/auth/config");
export const login = (username: string, password: string) =>
  send<{ token: string }>("/auth/login", "POST", { username, password });

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

export const generateCandidates = (eventId: string, language?: string) =>
  send<Candidate[]>(
    `/events/${eventId}/generate${language ? `?language=${language}` : ""}`,
    "POST",
  );
export const fetchCandidates = (eventId: string) =>
  getJSON<Candidate[]>(`/events/${eventId}/candidates`);

// ---- Publish workflow ----

export interface Prediction {
  id: string;
  predicted_at: string;
  model_version: string;
  viral_score: number;
  x_simulation: number;
  opportunity_score: number;
  predicted_impressions: number | null;
  predicted_likes: number | null;
  predicted_replies: number | null;
  predicted_reposts: number | null;
}

export interface Post {
  id: string;
  platform: string;
  external_id: string | null;
  text: string;
  status: string;
  origin: string;
  angle: string | null;
  event_id: string | null;
  created_at: string;
}

export interface ApproveResponse {
  post: Post;
  prediction: Prediction;
}

export const approveCandidate = (eventId: string, candidateId: string) =>
  send<ApproveResponse>(`/events/${eventId}/candidates/${candidateId}/approve`, "POST");
export const fetchPosts = (status?: string) =>
  getJSON<Post[]>(`/posts${status ? `?status=${status}` : ""}`);
export const markPosted = (postId: string, externalId: string) =>
  send<Post>(`/posts/${postId}/posted`, "POST", { external_id: externalId });

// ---- Evaluation ----

export interface EvaluationItem {
  post_id: string;
  text: string;
  predicted_likes: number;
  actual_likes: number;
  abs_error: number;
  error_pct: number;
  viral_score: number;
}

export interface EvaluationSummary {
  evaluated: number;
  mae: number;
  rmse: number;
  precision_at_3: number | null;
  items: EvaluationItem[];
}

export const fetchEvaluation = () => getJSON<EvaluationSummary>("/evaluation");

// ---- Notifications ----

export interface Notification {
  id: string;
  type: string;
  severity: string;
  title: string;
  body: string | null;
  event_id: string | null;
  read: boolean;
  created_at: string;
}

export const fetchNotifications = (unread = false) =>
  getJSON<Notification[]>(`/notifications${unread ? "?unread=true" : ""}`);
export const fetchUnreadCount = () => getJSON<number>("/notifications/unread-count");
export const markNotificationRead = (id: string) =>
  send<Notification>(`/notifications/${id}/read`, "POST");

// ---- Tweet tester ----

export interface TesterResponse {
  viral_potential: number;
  x_simulation: number;
  personal_fit: number;
  trend_fit: number;
  novelty: number;
  reply_potential: number;
  bookmark_potential: number;
  negative_risk: number;
  probabilities: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  scoring_version: string;
  disclaimer: string;
}

export const analyzeText = (text: string) =>
  send<TesterResponse>("/tester", "POST", { text });

// ---- Style profile ----

export interface StyleProfile {
  key: string;
  post_count: number;
  features: Record<string, number | string[]>;
  summary: string | null;
  updated_at: string;
}

export async function fetchProfile(): Promise<StyleProfile | null> {
  const res = await fetch(`${API_BASE}/profile`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<StyleProfile>;
}

export const rebuildProfile = () => send<StyleProfile>("/profile/rebuild", "POST");

// ---- Recommended action (PROJECT.md §31) ----

export function recommendedAction(opportunity: number): { label: string; tone: string } {
  if (opportunity >= 85) return { label: "POST NOW", tone: "hot" };
  if (opportunity >= 70) return { label: "POST WITHIN 30 MIN", tone: "good" };
  if (opportunity >= 50) return { label: "CONSIDER", tone: "warn" };
  return { label: "WAIT", tone: "muted" };
}
