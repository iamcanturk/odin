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
  source_types: string[];
  topics: string[];
  headlines: string[];
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
  suggested_image: string | null;
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
  minTrend?: number;
  q?: string;
}): Promise<EventList> {
  const qs = new URLSearchParams();
  qs.set("limit", String(params?.limit ?? 50));
  if (params?.status) qs.set("status", params.status);
  if (params?.orderBy) qs.set("order_by", params.orderBy);
  if (params?.minTrend) qs.set("min_trend", String(params.minTrend));
  if (params?.q?.trim()) qs.set("q", params.q.trim());
  return getJSON<EventList>(`/events?${qs.toString()}`);
}

export const dismissEvent = (id: string) =>
  send<{ id: string; status: string }>(`/events/${id}/dismiss`, "POST");

export async function fetchEvent(id: string): Promise<EventDetail | null> {
  const res = await fetch(`${API_BASE}/events/${id}`, {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (res.status === 404) return null; // deleted/dismissed event — not an API outage
  if (res.status === 401) handleUnauthorized(`/events/${id}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<EventDetail>;
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

export type TweetKind =
  | ""
  | "breaking"
  | "contrarian"
  | "technical"
  | "educational"
  | "question";

export type TweetLength = "short" | "long" | "story" | "thread";

export const generateCandidates = (
  eventId: string,
  opts?: {
    language?: string;
    kind?: TweetKind;
    length?: TweetLength;
    styleHandle?: string;
  },
) => {
  const qs = new URLSearchParams();
  if (opts?.language) qs.set("language", opts.language);
  if (opts?.kind) qs.set("kind", opts.kind);
  if (opts?.length) qs.set("length", opts.length);
  if (opts?.styleHandle) qs.set("style_handle", opts.styleHandle);
  const q = qs.toString();
  return send<Candidate[]>(`/events/${eventId}/generate${q ? `?${q}` : ""}`, "POST");
};
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

export const updateCandidate = (eventId: string, candidateId: string, text: string) =>
  send<Candidate>(`/events/${eventId}/candidates/${candidateId}`, "PATCH", { text });
export const deleteCandidate = (eventId: string, candidateId: string) =>
  send<void>(`/events/${eventId}/candidates/${candidateId}`, "DELETE");
export const updatePost = (postId: string, text: string) =>
  send<Post>(`/posts/${postId}`, "PATCH", { text });
export const deletePost = (postId: string) => send<void>(`/posts/${postId}`, "DELETE");

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
  calibration: number;
  bias: "under" | "over" | "none";
  impressions_per_like: number | null;
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

// ---- Sources ----

export interface Source {
  id: string;
  name: string;
  type: string;
  url: string | null;
  category: string | null;
  priority: string;
  enabled: boolean;
  poll_interval_seconds: number;
  confidence: number;
  last_polled_at: string | null;
  last_success_at: string | null;
  failure_count: number;
}

export const fetchSources = () => getJSON<Source[]>("/sources");
export const createSource = (body: {
  name: string;
  type: string;
  url?: string | null;
  category?: string | null;
}) => send<Source>("/sources", "POST", body);
export const updateSource = (id: string, body: { enabled?: boolean }) =>
  send<Source>(`/sources/${id}`, "PATCH", body);
export const deleteSource = (id: string) => send<void>(`/sources/${id}`, "DELETE");

// ---- Performance ----

export interface PerformanceCategory {
  category: string;
  score: number;
  posts: number;
  avg_engagement: number;
}
export interface PerformanceSummary {
  total_posts: number;
  by_type: PerformanceCategory[];
  by_topic: PerformanceCategory[];
}
export const fetchPerformance = () => getJSON<PerformanceSummary>("/performance");

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
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (res.status === 404) return null; // no profile yet — not an error
  if (res.status === 401) handleUnauthorized("/profile");
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<StyleProfile>;
}

export const rebuildProfile = () => send<StyleProfile>("/profile/rebuild", "POST");

// ---- Profile growth (PROJECT.md §12: follower/following over time) ----

export interface ProfilePoint {
  captured_at: string;
  followers: number | null;
  following: number | null;
  tweets: number | null;
}

export interface ProfileGrowth {
  handle: string | null;
  snapshots: number;
  latest: ProfilePoint | null;
  delta_followers: number | null;
  delta_following: number | null;
  series: ProfilePoint[];
}

export const fetchProfileGrowth = () => getJSON<ProfileGrowth>("/profile/growth");

// ---- Imported tweets (the user's own posts + metrics) ----

export interface ImportedTweet {
  id: string;
  external_id: string | null;
  text: string;
  url: string | null;
  posted_at: string | null;
  likes: number | null;
  reposts: number | null;
  replies: number | null;
  bookmarks: number | null;
  impressions: number | null;
}

export const fetchImportedTweets = () => getJSON<ImportedTweet[]>("/profile/tweets");

// ---- Best time to post ----

export interface TimeSlot {
  label: string;
  key: number;
  score: number;
  posts: number;
  avg_engagement: number;
}

export interface Timing {
  total_posts: number;
  enough_data: boolean;
  min_posts: number;
  best_hour: number | null;
  best_day: number | null;
  by_hour: TimeSlot[];
  by_day: TimeSlot[];
}

export const fetchTiming = () => getJSON<Timing>("/performance/timing");

// ---- Composer: generate posts about any topic ----

export type ComposeLength = "short" | "long" | "story" | "thread";
export type ComposeAudience = "technical" | "general";

export interface ComposeDraft {
  text: string;
  angle: string;
  viral_score: number;
  novelty_score: number;
  risk_score: number;
  rank: number;
}

export interface StyleRef {
  handle: string;
  samples: number;
}

export const fetchStyleRefs = () => getJSON<StyleRef[]>("/compose/styles");

export const refineText = (body: {
  text: string;
  instruction: string;
  language?: string;
  length?: ComposeLength;
  event_id?: string;
}) => send<{ text: string }>("/compose/refine", "POST", body);

export const compose = (body: {
  topic: string;
  language?: string;
  length?: ComposeLength;
  audience?: ComposeAudience;
  kind?: TweetKind;
  style_handle?: string;
}) => send<ComposeDraft[]>("/compose", "POST", body);

// ---- System / observability (PROJECT.md §44) ----

export interface CostBucket {
  purpose: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

export interface RunLog {
  kind: string;
  sources_polled: number;
  items_created: number;
  events_created: number;
  errors: string[];
  created_at: string;
}

export interface SystemStatus {
  cost_total_usd: number;
  cost_30d_usd: number;
  calls_total: number;
  tokens_total: number;
  by_purpose: CostBucket[];
  recent_runs: RunLog[];
}

export const fetchSystemStatus = () => getJSON<SystemStatus>("/system");

// ---- Recommended action (PROJECT.md §31) ----

export function recommendedAction(opportunity: number): { label: string; tone: string } {
  if (opportunity >= 85) return { label: "POST NOW", tone: "hot" };
  if (opportunity >= 70) return { label: "POST WITHIN 30 MIN", tone: "good" };
  if (opportunity >= 50) return { label: "CONSIDER", tone: "warn" };
  return { label: "WAIT", tone: "muted" };
}
