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
  cutout_url: string; // the real scan cutout
  photo_url: string; // what to show: a clean product shot of the same garment when there is one, else the cutout
  photo_drift: number | null; // ΔE between the product shot's measured colour and the scan's (the shot is used only under 20)
  source: string;
  scan_id: string;
  created_at: string;
  confidence: number | null;
  is_garment: boolean;
  user_edited: boolean;
  wear_count: number;
  last_worn: string | null;
  worn_estimated?: boolean; // last_worn is the user's estimate, not a logged wear
  tags: Tags | null;
  tag_error: string | null;
}

// Clean product shots of scanned items, made in the background after a scan (live mode).
export interface ProductStatus {
  done: number;
  running: number;
  waiting: number; // items that will get one next time the server runs live
  live: boolean;
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

// How the oni reads an event (closet/occasions.py): how dressed up, and when and where it is.
export interface OccasionRead {
  kind: string; // formal | funeral | interview | date | evening_out | work | active | gig | class | casual | everyday
  formality: number; // 0 sporty … 4 formal
  evening: boolean;
  outdoors: boolean;
  advice: string;
  why: string; // what the read was based on
  label: string; // e.g. "smart casual · evening · outdoors"
}

export interface UpcomingEvent extends CalendarEvent {
  day: string; // YYYY-MM-DD
  read: OccasionRead;
  plan_id: string | null; // looks already planned for it
  typed?: boolean; // typed in, not on the calendar
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
  trace: {
    provider?: string;
    model?: string;
    seconds?: number;
    cached?: boolean;
    prebuilt?: boolean; // made ahead of time, after a wear or check-in
    tokens_in?: number;
    tokens_out?: number;
    repairs?: number;
    failures?: string[];
    steps?: TraceStep[];
    taste?: { n: number; fit: number[] }; // how well each look suits the learned taste, %
    stretch?: { look: number; feature: string | null; label: string; pct: number; towards?: string | null }; // one step outside your comfort zone, maybe towards a style you want to grow into
  };
  weather_summary: string;
  plans_summary: string;
  looks: Look[];
  occasion: { event: CalendarEvent; read: OccasionRead } | null; // set when planned for one event, not the whole day
}

export interface Touch {
  play: string;
  kind: "underlayer" | "accessory" | "technique" | "colour";
  name: string;
  item: string;
  suggestion: string;
  why: string;
  needs: string[]; // basics keys, any one will do; empty for a technique
  owned: boolean;
  owned_label: string | null;
  example_url: string | null; // a picture of the idea (AI-made, the same for everyone)
}

export interface ColourRead {
  summary: string; // e.g. "all neutral · high contrast · cool"
  scheme: string;
  contrast: string;
  temperature: string;
  idea: string;
  plain: string; // the same read in everyday words, for the app
  palette: { item_id: string; name: string; hex: string; neutral: boolean }[];
}

export interface Touches {
  colour: ColourRead;
  recall: { id: string; name: string; text: string } | null; // a core piece the closet has none of: scan yours in
  touches: Touch[];
  source: "agent" | "rules";
  trace: { provider?: string; model?: string; seconds?: number; cached?: boolean };
}

export interface Style {
  basics: string[];
  skip: string[];
  catalog: { group: string; items: { key: string; label: string }[] }[];
}

export interface TraceStep {
  kind: "context" | "model" | "tool" | "check" | "repair" | "rules" | "done";
  label: string;
  detail: string;
  thought?: string | null; // an excerpt of the model's reasoning
  ms?: number;
  tokens?: number;
  ok?: boolean; // checks only
}

export type Mood = "starving" | "restless" | "calm" | "proud" | "fed" | "sleepy";

export interface Oni {
  mood: Mood;
  closet_alive_pct: number;
  garments: number;
  has_history: boolean; // any logged or estimated wear: without one the % is meaningless and hidden
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
  sample_removed?: number; // sample-closet pieces this real scan replaced
  warnings?: string[]; // e.g. light clothes on a light background
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
  taste_fit?: number; // how well the outfits it would make suit the learned taste, %
}

export interface TasteTrait {
  feature: string;
  label: string;
  weight: number;
  evidence: number;
  sure: boolean;
  sentence: string;
}

export interface StyleDna {
  signals: number;
  counts: Record<string, number>;
  traits: TasteTrait[];
  week: string[];
  narrative: string;
  narrative_source: "agent" | "rules";
  accuracy: { hits: number; n: number; accuracy: number; chance: number } | null;
  learning: string[];
  coverage: { worn: number; possible: number; pct: number };
  stretches_worn: number;
  styles: StylePicture;
}

// A piece on a collage board: one of your own garments, or a cut-out piece of a style board.
export interface BoardPiece {
  id: string;
  category: string; // top | bottom | outerwear | dress | shoes | bag | hat | eyewear | jewelry | accessory
  cutout_url: string;
  name?: string;
}

export interface StyleBoard {
  style: string;
  name: string;
  pieces: BoardPiece[];
}

export interface StyleShare {
  id: string;
  name: string;
  ja: string;
  pct: number;
  sure?: boolean;
}

export interface StylePicture {
  answers: number;
  liked: StyleShare[]; // from the style boards you picked
  closet: StyleShare[]; // what the outfits you wear already say
  grow: { id: string; name: string; ja: string; essence: string; signature: string[]; liked_pct: number; closet_pct: number } | null;
}

export interface QuizPair {
  a: Item[];
  b: Item[];
  a_extras: Item[]; // shoes / an accessory you own that go with it, for the collage only
  b_extras: Item[];
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

export type LayerStateName = "ready" | "pending" | "failed" | "missing" | "unsupported";

export interface LayerState {
  item_id: string;
  category: string;
  order: number; // stacking rank (closet/layering.py): bottoms ~100, base tops ~200, mid layers ~250, outerwear ~300
  state: LayerStateName;
  url?: string;
  box?: [number, number, number, number]; // x, y, w, h on the base image
  size?: [number, number];
  error?: string;
}

export interface LayersStatus {
  base_key: string;
  base: { state: LayerStateName; url?: string; size?: [number, number]; error?: string };
  layers: LayerState[];
  live: boolean;
  note: string | null;
}

export interface Place {
  name: string;
  lat: number;
  lon: number;
}

export interface Profile {
  location: Place | null;
  calendar: "none" | "sample" | "ics" | "link"; // link: a private iCal address that refreshes itself
  calendar_name: string | null; // the file name, or the link's host (the link itself never comes back)
  onboarded: boolean;
  wardrobe: Partial<Record<Category, number>>;
  can_plan: boolean; // a top + a bottom, or a dress
  tryon: TryOnProfile;
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

// On a server with a closet per device, the first response hands this browser its closet cookie.
// Ask once, before anything else, so the parallel requests of the first page load don't each get a new closet.
let handshake: Promise<unknown> | null = null;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    if (path !== "/api/closet") await (handshake ??= fetch("/api/closet").catch(() => null));
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "The oni can't reach your closet right now. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : friendly(res.status));
  }
  return body as T;
}

// When the server sends no explanation (it's down, restarting, or crashed), say so in plain words, never "500".
function friendly(status: number): string {
  if (status === 502 || status === 503 || status === 504 || status === 500)
    return "The oni's having a nap. Give it a moment, then try again.";
  if (status === 413) return "That photo is too big. Try a smaller one.";
  return "Something went wrong on the oni's side. Try again in a moment.";
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
  yesterday: () => call<{ plan: Plan | null }>("/api/yesterday"),
  answerYesterday: (look: number | null) => call<{ worn: WearResult | null }>("/api/yesterday", json("POST", { look })),
  checkin: (a: CheckinAnswers) => call<CheckinResult>("/api/checkins", json("POST", a)),
  wardrobe: () => call<Item[]>("/api/wardrobe"),
  products: () => call<ProductStatus>("/api/products"),
  makeProducts: () => call<ProductStatus>("/api/products", { method: "POST" }),
  setLastWorn: (items: { id: string; days_ago: number | null }[]) =>
    call<Item[]>("/api/wardrobe/last-worn", json("POST", { items })),
  deleteItem: (id: string) => call<void>(`/api/wardrobe/${id}`, { method: "DELETE" }),
  restoreItem: (id: string) => call<Item>(`/api/wardrobe/${id}/restore`, { method: "POST" }),
  choosePhoto: (id: string, use: "scan" | "redraw") => call<Item>(`/api/wardrobe/${id}/photo`, json("POST", { use })),
  // Correcting a piece: fix its tags by hand, ask the tagger again (with a hint), or replace its photo.
  fixItem: (id: string, changes: Partial<Tags>) => call<Item>(`/api/wardrobe/${id}`, json("PATCH", changes)),
  retagItem: (id: string, hint: string) => call<Item>(`/api/wardrobe/${id}/retag`, json("POST", { hint })),
  rescanItem: (id: string, photo: File) => {
    const form = new FormData();
    form.append("photo", photo, photo.name);
    return call<Item>(`/api/wardrobe/${id}/rescan`, { method: "POST", body: form });
  },
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
  tryonStack: (itemIds: string[]) =>
    call<{ base_key: string; layers: { item_id: string; url: string; order: number }[] }>("/api/tryon/layers/stack", json("POST", { item_ids: itemIds, prepare: false })),
  tryonLayers: (itemIds: string[], prepare = true) =>
    call<LayersStatus>("/api/tryon/layers", json("POST", { item_ids: itemIds, prepare })),
  flatlay: (planId: string, look: number) =>
    call<{ url: string }>(`/api/tryon/flatlay?plan_id=${encodeURIComponent(planId)}&look=${look}`),
  touches: (planId: string, look: number) => call<Touches>(`/api/plans/${planId}/touches?look=${look}`),
  style: () => call<Style>("/api/style"),
  updateStyle: (changes: { basics?: string[]; skip?: string[] }) => call<Style>("/api/style", json("PUT", changes)),
  gaps: (fresh = false) => call<Gaps>("/api/gaps", json("POST", { fresh })),
  thrift: () => call<ThriftEntry[]>("/api/thrift"),
  thriftExample: (p: GapPiece) =>
    call<{ url: string | null; cached: boolean; reason: string | null }>("/api/thrift/example", json("POST", { name: p.name, colors: p.colors, category: p.category })),
  addThrift: (piece: GapPiece, status: "watching" | "dismissed" = "watching") =>
    call<{ id: number }>("/api/thrift", json("POST", { piece, status })),
  setThrift: (id: number, status: ThriftStatus) => call<void>(`/api/thrift/${id}`, json("PATCH", { status })),
  removeThrift: (id: number) => call<void>(`/api/thrift/${id}`, { method: "DELETE" }),
  profile: () => call<Profile>("/api/profile"),
  updateProfile: (changes: { location?: Place; calendar?: Profile["calendar"]; onboarded?: boolean }) =>
    call<Profile>("/api/profile", json("PUT", changes)),
  uploadCalendar: (file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return call<{ events: number; today: CalendarEvent[]; profile: Profile }>("/api/profile/calendar", { method: "POST", body: form });
  },
  connectCalendar: (url: string) =>
    call<{ events: number; today: CalendarEvent[]; profile: Profile }>("/api/profile/calendar-link", json("POST", { url })),
  removeCalendar: () => call<Profile>("/api/profile/calendar", { method: "DELETE" }),
  occasions: () => call<{ calendar: Profile["calendar"]; events: UpcomingEvent[] }>("/api/occasions"),
  planOccasion: (event: CalendarEvent, day: string, fresh = false) =>
    call<Plan>("/api/occasions/plan", json("POST", { event, day, fresh })),
  plan: (id: string) => call<Plan>(`/api/plans/${id}`),
  geocode: (q: string) => call<Place[]>(`/api/geocode?q=${encodeURIComponent(q)}`),
  addPreference: (text: string, applies_when?: string) =>
    call<{ new: boolean }>("/api/preferences", json("POST", { text, applies_when: applies_when ?? null })),
  preferences: () => call<Preference[]>("/api/preferences"),
  forget: (id: number) => call<void>(`/api/preferences/${id}`, { method: "DELETE" }),
  taste: () => call<StyleDna>("/api/taste"),
  correctTaste: (feature: string, value: 1 | -1) => call<void>("/api/taste/correct", json("POST", { feature, value })),
  quiz: () => call<{ pairs: QuizPair[] }>("/api/taste/quiz"),
  styleQuiz: () => call<{ pairs: { a: StyleBoard; b: StyleBoard }[] }>("/api/styles/quiz"),
  answerStyleQuiz: (answers: { picked: string; other: string }[]) => call<{ saved: number }>("/api/styles/quiz", json("POST", { answers })),
  answerQuiz: (answers: { picked: string[]; other: string[] }[]) => call<{ saved: number }>("/api/taste/quiz", json("POST", { answers })),
  closet: () => call<{ per_device: boolean; id: string }>("/api/closet"),
  openCloset: (id: string) => call<{ id: string }>("/api/closet/open", json("POST", { id })),
  newCloset: () => call<{ id: string }>("/api/closet/new", { method: "POST" }),
  loadSample: () => call<{ imported: number }>("/api/closet/sample", { method: "POST" }),
  removeSample: () => call<{ removed: number }>("/api/closet/sample", { method: "DELETE" }),
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
