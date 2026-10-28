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
