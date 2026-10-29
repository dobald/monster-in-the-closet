import { useEffect, useRef, useState } from "react";
import { api, ApiError, itemName, type Item, type Place, type Plan, type Profile, type Scan } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";
import { LastWornList } from "./LastWorn";

// Getting started: meet the oni, then give it the things it needs to dress you (where you are,
// what's on today, what you own and roughly when you last wore it), and end on a real first pick.
// Who wears the try-on is asked the first time someone taps "Try it on", not here. Every step saves as you go, so leaving halfway loses nothing; "editing" reopens it from
// the location step (Notes → Your setup).

type Step = "hello" | "place" | "day" | "closet" | "history" | "first";
const STEPS: { id: Step; en: string; ja: string }[] = [
  { id: "hello", en: "HELLO", ja: "はじめまして" },
  { id: "place", en: "WEATHER", ja: "天気" },
  { id: "day", en: "YOUR DAY", ja: "予定" },
  { id: "closet", en: "CLOSET", ja: "服" },
  { id: "history", en: "LAST WORN", ja: "思い出" },
  { id: "first", en: "FIRST PICK", ja: "最初のコーデ" },
];

const RUNS: { id: "cold" | "neither" | "warm"; label: string; pref?: string }[] = [
  { id: "cold", label: "I run cold", pref: "Add a warmer layer; I run cold." },
  { id: "neither", label: "Neither" },
  { id: "warm", label: "I run warm", pref: "Choose lighter layers; I run warm." },
];

export default function Onboarding({ ctx, editing, onDone }: { ctx: AppCtx; editing: boolean; onDone: () => void }) {
  const steps = editing ? STEPS.filter((s) => s.id !== "hello") : STEPS;
  const [step, setStep] = useState<Step>(steps[0].id);
  const [profile, setProfile] = useState<Profile | null>(null);
  const i = steps.findIndex((s) => s.id === step);

  const refresh = () => api.profile().then(setProfile).catch((e) => ctx.toast((e as Error).message));
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const next = () => {
    refresh();
    setStep(steps[Math.min(i + 1, steps.length - 1)].id);
    window.scrollTo({ top: 0 });
  };
  const back = () => {
    setStep(steps[Math.max(i - 1, 0)].id);
    window.scrollTo({ top: 0 });
  };

  return (
    <main className="screen" style={{ minHeight: "100dvh", paddingBottom: "calc(24px + env(safe-area-inset-bottom))", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        {i > 0 ? (
          <button type="button" className="icon-btn press" aria-label="Back" onClick={back}>
            ←
          </button>
        ) : (
          <span />
        )}
        {/* The Japanese already sits in each step's vertical title; keep this line short so it never wraps. */}
        <span className="label" style={{ fontWeight: 400, whiteSpace: "nowrap" }}>
          STEP {i + 1} / {steps.length} · {steps[i].en}
        </span>
        {editing && (
          <button type="button" className="chip press" style={{ height: 32, fontSize: 12 }} onClick={onDone}>
            Close
          </button>
        )}
      </div>
      <div role="progressbar" aria-valuemin={1} aria-valuemax={steps.length} aria-valuenow={i + 1} style={{ display: "flex", gap: 4 }}>
        {steps.map((s, n) => (
          <span key={s.id} style={{ flex: 1, height: 6, borderRadius: 3, ...(n <= i ? { background: n === i ? "var(--shu)" : "var(--sumi)" } : { border: "var(--line)" }) }} />
        ))}
      </div>

      {!profile ? (
        <p className="small">Loading…</p>
      ) : (
        <div key={step} style={{ display: "flex", flexDirection: "column", gap: 14, flex: 1, animation: "rise .3s ease-out both" }}>
          {step === "hello" && <Hello profile={profile} onNext={next} />}
          {step === "place" && <PlaceStep profile={profile} ctx={ctx} onNext={next} />}
          {step === "day" && <DayStep profile={profile} ctx={ctx} onNext={next} />}
          {step === "closet" && <ClosetStep profile={profile} ctx={ctx} onChange={refresh} onNext={next} />}
          {step === "history" && <HistoryStep ctx={ctx} onNext={next} />}
          {step === "first" && <FirstPick profile={profile} ctx={ctx} editing={editing} onScan={() => setStep("closet")} onDone={onDone} />}
        </div>
      )}
    </main>
  );
}

// ------------------------------------------------------------------ shared bits

function Title({ en, ja, sub }: { en: string; ja: string; sub: string }) {
  return (
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 10 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <h1 className="display" style={{ fontSize: "clamp(34px, 11vw, 46px)", lineHeight: 0.95 }}>{en}</h1>
        <span style={{ fontSize: 14, lineHeight: 1.45 }}>{sub}</span>
      </div>
      <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 20 }}>{ja}</span>
    </header>
  );
}

function Bubble({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ margin: 0, flex: 1, border: "var(--line)", borderRadius: "12px 12px 12px 2px", padding: "10px 12px", fontSize: 15, lineHeight: 1.5, background: "var(--washi)" }}>
      {children}
    </p>
  );
}

function Footer({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingRight: 3 }}>{children}</div>
    </>
  );
}

function Option({ on, title, sub, onPick, children }: { on: boolean; title: string; sub: string; onPick: () => void; children?: React.ReactNode }) {
  return (
    <div
      style={{
        border: "var(--line)", borderRadius: 10, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8,
        ...(on ? { background: "var(--paper)", transform: "translate(2px, 2px)" } : { background: "var(--washi)", boxShadow: "2px 2px 0 var(--sumi)" }),
      }}
    >
      <button type="button" role="radio" aria-checked={on} onClick={onPick} style={{ display: "flex", gap: 10, alignItems: "flex-start", border: 0, background: "transparent", padding: 0, textAlign: "left" }}>
        <span aria-hidden="true" style={{ flex: "none", marginTop: 2, width: 18, height: 18, borderRadius: "50%", border: "var(--line)", background: on ? "radial-gradient(var(--sumi) 0 4px, var(--washi) 5px)" : "var(--washi)" }} />
        <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <strong style={{ fontSize: 15 }}>{title}</strong>
          <span className="small">{sub}</span>
        </span>
      </button>
      {on && children}
    </div>
  );
}

// ------------------------------------------------------------------ 1. hello

function Hello({ profile, onNext }: { profile: Profile; onNext: () => void }) {
  const has = Object.values(profile.wardrobe).reduce((a, b) => a + (b ?? 0), 0);
  const promises = [
    { k: "服", t: "Only what you own", s: "Outfits from your real closet. Never a shopping feed." },
    { k: "天", t: "Dressed for your day", s: "Weather and your calendar, every morning." },
    { k: "古", t: "Second-hand first", s: "When something's missing, I help you thrift it." },
  ];
  return (
    <>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <h1 className="display" style={{ fontSize: "clamp(56px, 19vw, 78px)", lineHeight: 0.9 }}>HELLO</h1>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 22 }}>はじめまして</span>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
        <Oni mood={has ? "calm" : "restless"} size={88} />
        <Bubble>
          Every closet app wants to style you. I'm the monster in yours, and I <strong>starve when your clothes go unworn</strong>. So every
          morning I dress you from what you already own, forgotten pieces first.
        </Bubble>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {promises.map((p, n) => (
          <div key={p.k} className="card" style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 12px", animation: `rise .35s ease-out ${0.1 + n * 0.08}s both` }}>
            <span lang="ja" className="hanko" style={{ width: 44, height: 44, fontSize: 20, flex: "none", transform: `rotate(${[-8, 5, -3][n]}deg)` }}>{p.k}</span>
            <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ fontSize: 15 }}>{p.t}</strong>
              <span className="small">{p.s}</span>
            </span>
          </div>
        ))}
      </div>
      <Footer>
        <button type="button" className="btn primary press block" style={{ height: 54 }} onClick={onNext}>
          Let's get started →
        </button>
        <span className="small muted" style={{ textAlign: "center" }}>
          About 3 minutes with a few photos, or 1 minute with the sample closet. No photo of you is ever needed.
        </span>
      </Footer>
    </>
  );
}

// ------------------------------------------------------------------ 2. where you are

function PlaceStep({ profile, ctx, onNext }: { profile: Profile; ctx: AppCtx; onNext: () => void }) {
  const [place, setPlace] = useState<Place | null>(profile.location);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [runs, setRuns] = useState<"cold" | "neither" | "warm" | null>(null);
  const [saving, setSaving] = useState(false);
  const canLocate = typeof window !== "undefined" && window.isSecureContext && "geolocation" in navigator;

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      setSearching(true);
      api.geocode(q).then(setResults).catch((e) => ctx.toast((e as Error).message)).finally(() => setSearching(false));
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const locate = () =>
    navigator.geolocation.getCurrentPosition(
      (p) => setPlace({ name: "My location", lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4) }),
      () => ctx.toast("Couldn't get your location. Search for your city instead."),
      { timeout: 8000 },
    );

  const save = async () => {
    if (!place) return;
    setSaving(true);
    try {
      await api.updateProfile({ location: place });
      const pref = RUNS.find((r) => r.id === runs)?.pref;
      if (pref) await api.addPreference(pref);
      onNext();
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Title en="WHERE ARE YOU?" ja="どこ？" sub="Weather decides the layers. I check it every morning for your city." />

      {place ? (
        <div className="card" style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, background: "var(--paper)" }}>
          <span className="tag-ai">{place.lat.toFixed(1)}°, {place.lon.toFixed(1)}°</span>
          <strong style={{ flex: 1, fontSize: 15 }}>{place.name}</strong>
          <button type="button" className="chip press" style={{ height: 30, fontSize: 12 }} onClick={() => setPlace(null)}>Change</button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, height: 48, padding: "0 14px", border: "var(--line)", borderRadius: 24, background: "var(--washi)" }}>
            <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Search for your city</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="6" />
              <path d="M20 20l-4.5-4.5" />
            </svg>
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your city, e.g. Toronto" style={{ flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent", fontSize: 15 }} />
            {searching && <span className="small muted">…</span>}
          </label>
          {results.length > 0 && (
            <div role="listbox" aria-label="Cities" className="card" style={{ overflow: "hidden" }}>
              {results.map((r, n) => (
                <button
                  key={`${r.lat},${r.lon}`}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => setPlace(r)}
                  style={{ display: "block", width: "100%", textAlign: "left", padding: "11px 14px", border: 0, borderTop: n ? "var(--line)" : 0, background: "transparent", fontSize: 14, fontWeight: 700 }}
                >
                  {r.name}
                </button>
              ))}
            </div>
          )}
          {canLocate && (
            <button type="button" className="chip press" style={{ alignSelf: "flex-start" }} onClick={locate}>
              Use my location
            </button>
          )}
        </div>
      )}

      <section aria-label="Cold or warm" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span className="label">DO YOU RUN COLD OR WARM?</span>
        <div role="radiogroup" aria-label="Cold or warm" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, paddingRight: 2 }}>
          {RUNS.map((r) => (
            <button key={r.id} type="button" role="radio" aria-checked={runs === r.id} className="chip press" style={{ height: 44, borderRadius: 8, padding: 0 }} onClick={() => setRuns(r.id)}>
              {r.label}
            </button>
          ))}
        </div>
        <span className="small muted">Optional. I'll learn the rest from your evening check-ins.</span>
      </section>

      <Footer>
        <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={!place || saving} onClick={save}>
          {place ? "Next →" : "Pick your city first"}
        </button>
      </Footer>
    </>
  );
}

// ------------------------------------------------------------------ 3. your day

function DayStep({ profile, ctx, onNext }: { profile: Profile; ctx: AppCtx; onNext: () => void }) {
  // First run defaults to "just weather": most people don't know what an .ics file is. Editing keeps the saved choice.
  const [kind, setKind] = useState<Profile["calendar"]>(profile.onboarded || profile.calendar === "ics" ? profile.calendar : "none");
  const [fileName, setFileName] = useState(profile.calendar_name);
  const [uploaded, setUploaded] = useState<{ events: number; today: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const upload = async (f: File) => {
    setBusy(true);
    try {
      const r = await api.uploadCalendar(f);
      setFileName(f.name);
      setUploaded({ events: r.events, today: r.today.map((e) => `${e.start} ${e.title}`) });
      setKind("ics");
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      if (kind !== "ics") await api.updateProfile({ calendar: kind });
      onNext();
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const hasIcs = kind === "ics" && !!fileName;
  return (
    <>
      <Title en="WHAT'S ON?" ja="予定" sub="I dress you for your plans too: a crit, a dinner out, a date." />
      <div role="radiogroup" aria-label="Calendar" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <Option on={kind === "none"} title="Just weather" sub="No calendar needed. You can add one later in Notes." onPick={() => setKind("none")} />
        <Option on={kind === "ics"} title="Add my calendar" sub="An .ics file from Google Calendar or Apple Calendar." onPick={() => setKind("ics")}>
          <span className="small">
            Google: Settings → Import &amp; export → Export, then unzip. Apple: File → Export → Export.
          </span>
          <input ref={input} type="file" accept=".ics,text/calendar" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
          <button type="button" className="btn press" style={{ height: 44 }} disabled={busy} onClick={() => input.current?.click()}>
            {busy ? "Reading it…" : hasIcs ? "Choose a different file" : "Choose calendar file"}
          </button>
          {hasIcs && (
            <span className="small">
              <strong>{fileName}</strong>{uploaded ? ` · ${uploaded.events} event${uploaded.events === 1 ? "" : "s"}` : ""}.{" "}
              {uploaded && (uploaded.today.length ? `Today: ${uploaded.today.join(", ")}.` : "Nothing on today.")}
            </span>
          )}
        </Option>
        <Option on={kind === "sample"} title="Use the demo calendar" sub="A studio crit at 10:00 and dinner outside at 19:00, every day." onPick={() => setKind("sample")} />
      </div>
      <span className="small muted">Only event titles, times and places are read. The file stays in your closet's private storage.</span>
      <Footer>
        <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={busy || (kind === "ics" && !hasIcs)} onClick={save}>
          {kind === "ics" && !hasIcs ? "Choose a file, or pick another option" : "Next →"}
        </button>
      </Footer>
    </>
  );
}

// ------------------------------------------------------------------ 4. feed me clothes

function ClosetStep({ profile, ctx, onChange, onNext }: { profile: Profile; ctx: AppCtx; onChange: () => void; onNext: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [scan, setScan] = useState<Scan | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const w = profile.wardrobe;
  const total = Object.values(w).reduce((a, b) => a + (b ?? 0), 0);

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.scan(files);
      setScan(r);
      setFiles([]);
      ctx.bumpWardrobe();
      onChange();
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const sample = async () => {
    setBusy(true);
    try {
      await api.loadSample();
      ctx.bumpWardrobe();
      onChange();
      ctx.toast("Loaded 9 sample pieces. Some haven't been worn in months, so there's plenty to rescue.");
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Title en="FEED ME CLOTHES" ja="服をちょうだい" sub="Photograph your clothes laid flat, a few at a time. I find each piece and learn what it is." />

      {busy ? (
        <div className="halftone card" style={{ height: 260, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
          <Oni mood="calm" size={80} />
          <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700 }}>
            <span className="spinner-dots">Finding your clothes</span>
          </span>
          {ctx.health?.mode === "live" && <span className="label" style={{ background: "var(--washi)", padding: "2px 6px" }}>SAM 3.1 + MUSE SPARK · ~30–60S</span>}
        </div>
      ) : scan ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Oni mood="fed" size={60} />
            <h2 className="display" style={{ fontSize: 30 }}>FOUND {scan.items.length}!</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
            {scan.items.map((it, n) => (
              <span key={it.id} className="halftone" title={itemName(it)} style={{ aspectRatio: "1", border: "var(--line)", borderRadius: 8, padding: 4, animation: `rise .3s ease-out ${n * 0.05}s both` }}>
                <img className="cutout" src={it.cutout_url} alt={itemName(it)} />
              </span>
            ))}
          </div>
          {!!scan.duplicates?.merged.length && <span className="small">{scan.duplicates.merged.length} were already in your closet, so I merged them.</span>}
        </div>
      ) : (
        <>
          <FlatLayGuide />
          <DataNote />
        </>
      )}

      {total > 0 && (
        <div className="card" style={{ padding: "10px 12px", display: "flex", gap: 10, alignItems: "center" }}>
          <span className="display" style={{ fontSize: 26 }}>{total}</span>
          <span className="small">
            pieces in your closet
            {` (${[w.top && `${w.top} top${w.top > 1 ? "s" : ""}`, w.bottom && `${w.bottom} bottom${w.bottom > 1 ? "s" : ""}`, w.dress && `${w.dress} dress${w.dress > 1 ? "es" : ""}`, w.outerwear && `${w.outerwear} layer${w.outerwear > 1 ? "s" : ""}`].filter(Boolean).join(", ")})`}
          </span>
        </div>
      )}

      <input ref={input} type="file" accept="image/*,.heic,.heif" multiple hidden onChange={(e) => { setFiles(Array.from(e.target.files ?? []).slice(0, 10)); setScan(null); e.target.value = ""; }} />
      <Footer>
        {files.length > 0 ? (
          <button type="button" className="btn shu press block" style={{ height: 52 }} disabled={busy} onClick={run}>
            Scan {files.length} photo{files.length > 1 ? "s" : ""} →
          </button>
        ) : (
          <button type="button" className={"btn press block " + (profile.can_plan ? "" : "shu")} style={{ height: 52 }} disabled={busy} onClick={() => input.current?.click()}>
            {total ? "Scan another batch" : "Take or choose photos"}
          </button>
        )}
        {!total && !files.length && (
          <button type="button" className="btn press block" style={{ height: 52 }} disabled={busy} onClick={sample}>
            No clothes handy? Try a sample closet
          </button>
        )}
        {profile.can_plan ? (
          <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={busy} onClick={onNext}>
            Next →
          </button>
        ) : (
          <span className="small muted" style={{ textAlign: "center" }}>
            I need at least one top and one bottom (or a dress) to dress you.{" "}
            <button type="button" onClick={onNext} style={{ border: 0, background: "none", padding: 0, textDecoration: "underline", fontSize: "inherit", color: "inherit" }}>
              I'll scan later
            </button>
          </span>
        )}
      </Footer>
    </>
  );
}

// What happens to the photos, said up front for testers trying a friend's build.
export function DataNote() {
  const [perDevice, setPerDevice] = useState<boolean | null>(null);
  useEffect(() => {
    api.closet().then((c) => setPerDevice(c.per_device)).catch(() => {});
  }, []);
  return (
    <p className="small muted" style={{ margin: 0, lineHeight: 1.5 }}>
      <strong>Your photos:</strong> Meta's AI models (SAM 3.1 and Muse Spark) cut out and tag each piece.{" "}
      {perDevice
        ? "The cutouts stay on this app's server, in a closet only your device can open. Nobody else sees them."
        : "The cutouts are kept on the computer running this app, in one shared closet."}
    </p>
  );
}

// A little drawing of a good flat-lay, plus the three rules that make scans work.
function FlatLayGuide() {
  const pieces = [
    { x: 14, y: 14, w: 34, h: 30, r: -4, c: "var(--ai)" },
    { x: 54, y: 10, w: 32, h: 40, r: 3, c: "var(--sumi)" },
    { x: 12, y: 52, w: 26, h: 38, r: 2, c: "var(--shu)" },
    { x: 46, y: 58, w: 40, h: 28, r: -3, c: "var(--ghost)" },
  ];
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
      <div aria-hidden="true" style={{ position: "relative", flex: "none", width: 128, aspectRatio: "1", border: "var(--line)", borderRadius: 10, background: "var(--cam)" }}>
        <span style={{ position: "absolute", inset: 6, border: "2px dashed var(--washi)", borderRadius: 8 }} />
        {pieces.map((p, n) => (
          <span key={n} style={{ position: "absolute", left: `${p.x}%`, top: `${p.y}%`, width: `${p.w}%`, height: `${p.h}%`, background: p.c, border: "1.5px solid var(--sumi)", borderRadius: 4, transform: `rotate(${p.r}deg)` }} />
        ))}
      </div>
      <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", justifyContent: "center", gap: 6, fontSize: 14, lineHeight: 1.35 }}>
        <li><strong>4–8 pieces</strong> flat on a bed or the floor</li>
        <li><strong>No overlaps:</strong> leave a gap around each</li>
        <li><strong>Print side up</strong>, in good light</li>
      </ol>
    </div>
  );
}

// ------------------------------------------------------------------ 5. when did you last wear these

function HistoryStep({ ctx, onNext }: { ctx: AppCtx; onNext: () => void }) {
  const [items, setItems] = useState<Item[] | null>(null);
  useEffect(() => {
    api.wardrobe().then(setItems).catch((e) => ctx.toast((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // "A while ago" for everything without an answer yet: good enough for the oni to start rescuing, and fixable later.
  const guess = async () => {
    const open = (items ?? []).filter((i) => !i.last_worn);
    try {
      if (open.length) {
        await api.setLastWorn(open.map((i) => ({ id: i.id, days_ago: 60 })));
        ctx.bumpWardrobe();
      }
    } catch (e) {
      ctx.toast((e as Error).message);
    }
    onNext();
  };
  return (
    <>
      <Title en="WHEN DID YOU LAST WEAR THESE?" ja="思い出" sub="A rough guess is fine. It's how I know what you've forgotten, so I can bring it back." />
      {!items ? (
        <p className="small">Loading…</p>
      ) : items.length === 0 ? (
        <Footer>
          <button type="button" className="btn primary press block" onClick={onNext}>Next →</button>
        </Footer>
      ) : (
        <LastWornList
          items={items}
          cta="Next →"
          onError={ctx.toast}
          onSaved={(updated) => {
            if (updated.length) ctx.bumpWardrobe();
            onNext();
          }}
        />
      )}
      <button type="button" onClick={guess} className="small" style={{ border: 0, background: "none", textDecoration: "underline", color: "inherit", alignSelf: "center", padding: 4 }}>
        Not sure? Guess for me
      </button>
    </>
  );
}

// ------------------------------------------------------------------ 6. first pick

function FirstPick({ profile, ctx, editing, onScan, onDone }: { profile: Profile; ctx: AppCtx; editing: boolean; onScan: () => void; onDone: () => void }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const asked = useRef(false); // one plan per visit: React runs effects twice in dev, and a live plan costs a model call

  useEffect(() => {
    if (!profile.can_plan || asked.current) return;
    asked.current = true;
    api.makePlan("").then(setPlan).catch((e) => setError(e instanceof ApiError ? e.message : (e as Error).message));
  }, [profile.can_plan]);

  const finish = async () => {
    setFinishing(true);
    try {
      await api.updateProfile({ onboarded: true });
      onDone();
    } catch (e) {
      ctx.toast((e as Error).message);
      setFinishing(false);
    }
  };

  const look = plan?.looks[0];
  return (
    <>
      <Title en="YOUR FIRST PICK" ja="最初のコーデ" sub={editing ? "Here's today with your new setup." : "Everything's set. Here's what I'd put you in today."} />

      {!profile.can_plan ? (
        <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10, alignItems: "center", textAlign: "center" }}>
          <Oni mood="restless" size={70} />
          <span>I can't dress you yet: scan at least one top and one bottom.</span>
          <button type="button" className="btn shu press block" onClick={onScan}>Scan my clothes →</button>
        </div>
      ) : error ? (
        <p className="small" style={{ color: "var(--shu)", fontWeight: 700 }}>{error}</p>
      ) : !look ? (
        <div className="halftone card" style={{ height: 300, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
          <Oni mood="calm" size={80} />
          <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700 }}>
            <span className="spinner-dots">Checking the weather and your day</span>
          </span>
        </div>
      ) : (
        <article className="card" style={{ position: "relative", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          <span lang="ja" className="hanko" style={{ position: "absolute", top: -16, right: 10, animation: "stamp .5s cubic-bezier(.2,.9,.3,1.2) .3s both" }}>選</span>
          <span className="small" style={{ paddingRight: 64, fontWeight: 700 }}>{plan!.weather_summary}</span>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(look.items.length, 4)}, minmax(0, 1fr))`, gap: 8 }}>
            {look.items.slice(0, 4).map((it: Item, n) => (
              <span key={it.id} className="halftone" style={{ aspectRatio: "3 / 4", border: "var(--line)", borderRadius: 8, padding: 6, transform: `rotate(${[-3, 2, -1, 3][n]}deg)`, animation: `rise-tilt .4s ease-out ${n * 0.08}s both` }}>
                <img className="cutout" src={it.cutout_url} alt={itemName(it)} />
              </span>
            ))}
          </div>
          <h2 className="display" style={{ fontSize: 22 }}>{look.name}</h2>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>{look.why}</p>
          {plan!.calendar.events.length > 0 && <span className="small muted">For: {plan!.plans_summary}</span>}
        </article>
      )}

      <Footer>
        <button type="button" className="btn primary press block" style={{ height: 54 }} disabled={finishing || (profile.can_plan && !look && !error)} onClick={finish}>
          {editing ? "Done →" : profile.can_plan ? "See my day →" : "Finish setup for now"}
        </button>
        {!editing && <span className="small muted" style={{ textAlign: "center" }}>Tonight I'll ask how it went, and get better every day.</span>}
      </Footer>
    </>
  );
}
