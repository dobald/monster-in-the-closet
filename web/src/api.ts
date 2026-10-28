// Typed client for the FastAPI backend. Shapes mirror server/main.py.

export type Category = "top" | "bottom" | "dress" | "outerwear" | "shoes" | "accessory" | "other";

export interface Tags {
  is_garment: boolean;
  category: Category;
  subtype: string;
  primary_color: string;
  secondary_colors: string[];
  pattern: string;
  material_guess: string;
  warmth: number;
  formality: string;
  seasons: string[];
  fit: string;
  distinctive_details: string;
  visible_side: string;
  print_side: string;
  confidence: number;
}

export interface Item {
  id: string;
  cutout_url: string;
  source: string;
  scan_id: string;
  created_at: string;
  confidence: number | null;
  is_garment: boolean;
  user_edited: boolean;
  wear_count: number;
  last_worn: string | null;
  tags: Tags | null;
  tag_error: string | null;
}

export interface WeatherPart {
  temp_c: [number, number];
  feels_like_low_c: number;
  rain_chance_pct: number;
  sky: string;
}

export interface CalendarEvent {
  start: string;
  end?: string;
  title: string;
  location?: string;
  dress_code?: string;
}

export interface Look {
  name: string;
  item_ids: string[];
  why: string;
  rediscovered_id: string | null;
  items: Item[];
}

export interface Plan {
  id: string;
  day: string;
  source: "agent" | "rules" | "cache";
  notes: string;
  weather: { parts?: Record<"morning" | "afternoon" | "evening", WeatherPart> };
  calendar: { events: CalendarEvent[] };
  trace: { provider?: string; model?: string; seconds?: number; cached?: boolean };
  weather_summary: string;
  plans_summary: string;
  looks: Look[];
}

export type Mood = "restless" | "calm" | "proud" | "fed" | "sleepy";

export interface Oni {
  mood: Mood;
  closet_alive_pct: number;
  garments: number;
  forgotten: number;
  streak_days: number;
}

export interface WearResult {
  day: string;
  look: Look;
  rescued: { id: string; name: string; days: number }[];
  closet_alive_before: number;
  closet_alive_after: number;
  streak_days: number;
  oni: Oni;
}

export interface CheckinAnswers {
  plan_id?: string;
  temperature: "cold" | "just_right" | "warm";
  feeling: "meh" | "fine" | "good" | "iconic";
  tags: string[];
  note: string;
}

export interface CheckinResult {
  id: string;
  oni_reply: string;
  learned: { preference: string | null; applies_when: string | null } | null;
  new_preference: boolean;
}

export interface Preference {
  id: number;
  created_at: string;
  text: string;
  applies_when: string | null;
}

export interface DuplicatePair {
  a: Item;
  b: Item;
  checked: boolean; // false: no model verdict yet (fixture mode)
  confidence: number | null;
  reason: string;
}

export interface Duplicates {
  merged: { kept: Item; dropped_id: string; confidence: number; reason: string }[];
  review: DuplicatePair[];
  checked: number;
}

export interface Scan {
  id: string;
  mode: string;
  seconds: number;
  photos: number;
  cached_photos: number;
  replayed: boolean;
  dropped: { source: string; reason: string }[];
  items: Item[];
  duplicates: Duplicates | null;
}

export interface GapPiece {
  name: string;
  category: "top" | "bottom" | "dress" | "outerwear";
  colors: string[];
  pairs_with: string[];
  why: string;
  look_for: string;
  price_range: string;
  search_terms: string[];
  outfits_unlocked: number;
  pairs: Item[];
  example_url?: string | null; // AI example photo, once made
}

export interface Gaps {
  created_at: string;
  source: "agent" | "rules";
  summary: string;
  pieces: GapPiece[];
  trace: { provider?: string; seconds?: number; cached?: boolean };
}

export type ThriftStatus = "watching" | "found" | "dismissed";

export interface ThriftEntry {
  id: number;
  created_at: string;
  name: string;
  status: ThriftStatus;
  piece: GapPiece;
}

export type TryOnMode = "mannequin" | "photo" | "flat";

export interface BodyProfile {
  height_cm: number;
  build: "slim" | "regular" | "athletic" | "curvy" | "plus";
  silhouette: "feminine" | "masculine" | "neutral";
  skin_tone: number; // 1-8, the mannequin's finish
}

export interface TryOnProfile {
  mode: TryOnMode;
  body: BodyProfile | null;
  ready: boolean;
  photo: { checked_at: string; advice: string } | null;
}

export interface PhotoCheck {
  ok: boolean;
  advice: string;
  one_person: boolean;
  full_body: boolean;
  face_visible: boolean;
}

export interface TryOnJob {
  id: string;
  status: "running" | "done" | "failed";
  step?: string;
  look_name: string;
  mode: TryOnMode;
  flatlay_url: string;
  render_url: string | null;
  cached: boolean;
  score: number | null;
  attempts: number;
  differences: string[];
  seconds: number | null;
  error: string | null;
  note: string | null;
}

export interface Health {
  ok: boolean;
  mode: "fixture" | "live";
  garments: number;
  scans: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Can't reach the closet server. Is the API running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return body as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  health: () => call<Health>("/api/health"),
  oni: () => call<Oni>("/api/oni"),
  latestPlan: () => call<Plan>("/api/plan"),
  makePlan: (notes = "", fresh = false) => call<Plan>("/api/plan", json("POST", { notes, fresh })),
  wear: (planId: string, look: number) => call<WearResult>(`/api/plans/${planId}/wear`, json("POST", { look })),
  checkin: (a: CheckinAnswers) => call<CheckinResult>("/api/checkins", json("POST", a)),
  wardrobe: () => call<Item[]>("/api/wardrobe"),
  deleteItem: (id: string) => call<void>(`/api/wardrobe/${id}`, { method: "DELETE" }),
  findDuplicates: () => call<Duplicates>("/api/wardrobe/duplicates/check", { method: "POST" }),
  mergeItems: (a: string, b: string) => call<Item>("/api/wardrobe/duplicates/merge", json("POST", { a, b })),
  notDuplicates: (a: string, b: string) => call<void>("/api/wardrobe/duplicates/distinct", json("POST", { a, b })),
  tryonProfile: () => call<TryOnProfile>("/api/tryon/profile"),
  setTryonProfile: (mode: TryOnMode, body?: BodyProfile) =>
    call<TryOnProfile>("/api/tryon/profile", json("PUT", { mode, body: body ?? null })),
  uploadPersonPhoto: (photo: File, consent: boolean) => {
    const form = new FormData();
    form.append("photo", photo, photo.name);
    form.append("consent", String(consent));
    return call<PhotoCheck>("/api/tryon/photo", { method: "POST", body: form });
  },
  deletePersonPhoto: () => call<{ renders_deleted: number }>("/api/tryon/photo", { method: "DELETE" }),
  startTryon: (planId: string, look: number) => call<TryOnJob>("/api/tryon", json("POST", { plan_id: planId, look })),
  tryonJob: (id: string) => call<TryOnJob>(`/api/tryon/jobs/${id}`),
  gaps: (fresh = false) => call<Gaps>("/api/gaps", json("POST", { fresh })),
  thrift: () => call<ThriftEntry[]>("/api/thrift"),
  thriftExample: (p: GapPiece) =>
    call<{ url: string | null; cached: boolean; reason: string | null }>("/api/thrift/example", json("POST", { name: p.name, colors: p.colors, category: p.category })),
  addThrift: (piece: GapPiece, status: "watching" | "dismissed" = "watching") =>
    call<{ id: number }>("/api/thrift", json("POST", { piece, status })),
  setThrift: (id: number, status: ThriftStatus) => call<void>(`/api/thrift/${id}`, json("PATCH", { status })),
  removeThrift: (id: number) => call<void>(`/api/thrift/${id}`, { method: "DELETE" }),
  preferences: () => call<Preference[]>("/api/preferences"),
  forget: (id: number) => call<void>(`/api/preferences/${id}`, { method: "DELETE" }),
  scan: (photos: File[]) => {
    const form = new FormData();
    photos.forEach((p) => form.append("photos", p, p.name));
    return call<Scan>("/api/scans", { method: "POST", body: form });
  },
};

// ---- small helpers shared by screens

export function idleDays(item: Item, today = new Date()): number {
  const ref = item.last_worn ?? item.created_at;
  const d = new Date(ref.length === 10 ? ref + "T00:00:00" : ref);
  return Math.max(0, Math.floor((today.getTime() - d.getTime()) / 86_400_000));
}

export function itemName(item: Item): string {
  if (!item.tags) return "Untagged item";
  const name = `${item.tags.primary_color} ${item.tags.subtype}`;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function shortName(item: Item): string {
  if (!item.tags) return "Item";
  const words = item.tags.subtype.split(" ");
  const s = words.slice(-2).join(" ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
