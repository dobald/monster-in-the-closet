import { useEffect, useRef, useState } from "react";
import { api, itemName, shortName, type BodyProfile, type LayersStatus, type PhotoCheck, type Plan, type TryOnJob, type TryOnMode, type TryOnProfile } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

// Try-on (wireframe 2d): who wears it (mannequin by default, your photo only by opt-in, or no body
// at all). The mannequin is dressed from per-garment layers stacked on one base image, so swapping
// looks or taking a piece off is instant; the exact full render and the flat-lay are a tap away.

const TONES: [string, string][] = [
  ["#F6DCC9", "Pale ivory"], ["#EBC3A4", "Light beige"], ["#D9A57E", "Sand"], ["#C08A5E", "Warm tan"],
  ["#A26E45", "Caramel brown"], ["#80522F", "Chestnut brown"], ["#5E3A20", "Dark brown"], ["#3F2614", "Deep espresso"],
];
const BUILDS: BodyProfile["build"][] = ["slim", "regular", "athletic", "curvy", "plus"];
const FORMS: BodyProfile["silhouette"][] = ["feminine", "masculine", "neutral"];
const MODES: { id: TryOnMode; title: string; sub: string; badge?: string }[] = [
  { id: "mannequin", title: "Mannequin", sub: "No photo. A faceless stand-in from a few details.", badge: "DEFAULT" },
  { id: "photo", title: "My photo", sub: "The face version. Opt-in, deletable." },
  { id: "flat", title: "Flat-lay only", sub: "Just your clothes, no body." },
];
const DEFAULT_BODY: BodyProfile = { height_cm: 170, build: "regular", silhouette: "neutral", skin_tone: 4 };
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function TryOn({ plan, lookIndex, setupOnly, ctx, onClose }: {
  plan: Plan | null; lookIndex: number | null; setupOnly: boolean; ctx: AppCtx; onClose: () => void;
}) {
  const [profile, setProfile] = useState<TryOnProfile | null>(null);
  const [view, setView] = useState<"loading" | "setup" | "result" | "dress">("loading");
  const [job, setJob] = useState<TryOnJob | null>(null);
  const canRender = plan !== null && lookIndex !== null;

  const start = async () => {
    if (!canRender) return;
    setView("result");
    setJob(null);
    try {
      setJob(await api.startTryon(plan!.id, lookIndex!));
    } catch (e) {
      ctx.toast((e as Error).message);
      setView("setup");
    }
  };

  useEffect(() => {
    api.tryonProfile().then((p) => {
      setProfile(p);
      if (setupOnly || !p.ready || !canRender) setView("setup");
      else if (p.mode === "mannequin") setView("dress");
      else start();
    }).catch((e) => ctx.toast((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll a running render.
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setTimeout(() => api.tryonJob(job.id).then(setJob).catch((e) => setJob({ ...job, status: "failed", error: (e as Error).message })), 2000);
    return () => clearTimeout(t);
  }, [job]);

  const look = canRender ? plan!.looks[lookIndex!] : null;

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Try-on">
      <div className="sheet">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            TRY-ON · <span lang="ja">試着</span>
            {look && view !== "dress" ? ` · ${look.name.toUpperCase()}` : ""}
          </span>
        </div>

        {view === "loading" && <p className="small">Loading…</p>}
        {view === "setup" && profile && (
          <Setup
            profile={profile}
            ctx={ctx}
            cta={canRender && !setupOnly ? "Save & try it on →" : "Save"}
            onSaved={(p) => {
              setProfile(p);
              if (canRender && !setupOnly) {
                if (p.mode === "mannequin") setView("dress");
                else start();
              }
              else {
                ctx.toast("Try-on settings saved.");
                onClose();
              }
            }}
          />
        )}
        {view === "result" && <Result job={job} mode={profile?.mode ?? "mannequin"} onSetup={() => setView("setup")} onClose={onClose} />}
        {view === "dress" && canRender && <DressUp plan={plan!} initialLook={lookIndex!} ctx={ctx} onSetup={() => setView("setup")} onClose={onClose} />}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ setup

function Setup({ profile, ctx, cta, onSaved }: { profile: TryOnProfile; ctx: AppCtx; cta: string; onSaved: (p: TryOnProfile) => void }) {
  const [mode, setMode] = useState<TryOnMode>(profile.mode);
  const [body, setBody] = useState<BodyProfile>(profile.body ?? DEFAULT_BODY);
  const [photo, setPhoto] = useState(profile.photo);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [check, setCheck] = useState<PhotoCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const save = async () => {
    setBusy(true);
    try {
      if (mode === "photo" && file) {
        const result = await api.uploadPersonPhoto(file, consent);
        setCheck(result);
        if (!result.ok) return;
      }
      onSaved(await api.setTryonProfile(mode, mode === "mannequin" ? body : undefined));
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const removePhoto = async () => {
    const r = await api.deletePersonPhoto();
    setPhoto(null);
    setFile(null);
    setPreview(null);
    setCheck(null);
    ctx.toast(`Photo deleted${r.renders_deleted ? `, with ${r.renders_deleted} render${r.renders_deleted === 1 ? "" : "s"} made from it` : ""}.`);
  };

  const photoReady = mode !== "photo" || (file ? consent : photo !== null);

  return (
    <>
      <header style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h1 className="display" style={{ fontSize: 40, lineHeight: 1 }}>WHO WEARS IT?</h1>
        <span className="small">
          Try-on setup · <span lang="ja">試着の設定</span> · change anytime
        </span>
      </header>

      <div role="radiogroup" aria-label="Try-on mode" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {MODES.map((m) => {
          const on = mode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={on}
              className="press"
              onClick={() => setMode(m.id)}
              style={{
                display: "flex", alignItems: "center", gap: 10, minHeight: 54, padding: "6px 12px", border: "var(--line)", borderRadius: 10,
                textAlign: "left", ...(on ? { background: "var(--paper)", transform: "translate(2px, 2px)" } : { background: "var(--washi)", boxShadow: "2px 2px 0 var(--sumi)" }),
              }}
            >
              <span aria-hidden="true" style={{ flex: "none", width: 18, height: 18, borderRadius: "50%", border: "var(--line)", background: on ? "radial-gradient(var(--sumi) 0 4px, var(--washi) 5px)" : "var(--washi)" }} />
              <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 1 }}>
                <strong style={{ fontSize: 15 }}>{m.title}</strong>
                <span className="small">{m.sub}</span>
              </span>
              {m.badge && <span className="label" style={{ fontSize: 9, border: "var(--line)", borderRadius: 4, padding: "2px 5px" }}>{m.badge}</span>}
            </button>
          );
        })}
      </div>

      {mode === "mannequin" && (
        <section aria-label="Mannequin details" style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
          <Figure body={body} />
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="label">HEIGHT {body.height_cm} CM</span>
              <input type="range" min={140} max={210} value={body.height_cm} onChange={(e) => setBody({ ...body, height_cm: Number(e.target.value) })} style={{ accentColor: "var(--sumi)" }} />
            </label>
            <Options label="BUILD" values={BUILDS} value={body.build} onPick={(v) => setBody({ ...body, build: v })} />
            <Options label="FORM" values={FORMS} value={body.silhouette} onPick={(v) => setBody({ ...body, silhouette: v })} />
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="label">FINISH · {TONES[body.skin_tone - 1][1].toUpperCase()}</span>
              <div role="radiogroup" aria-label="Mannequin finish" style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {TONES.map(([hex, name], i) => (
                  <button
                    key={hex}
                    type="button"
                    role="radio"
                    aria-checked={body.skin_tone === i + 1}
                    aria-label={name}
                    onClick={() => setBody({ ...body, skin_tone: i + 1 })}
                    style={{ width: 28, height: 28, borderRadius: "50%", border: "var(--line)", background: hex, padding: 0, boxShadow: body.skin_tone === i + 1 ? "0 0 0 2px var(--washi), 0 0 0 4px var(--sumi)" : "none" }}
                  />
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {mode === "photo" && (
        <section aria-label="Your photo" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {photo && !file ? (
            <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              <strong>Photo on file ✓</strong>
              <span className="small">Checked {new Date(photo.checked_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}. {photo.advice}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="chip press" onClick={() => input.current?.click()}>Use a different photo</button>
                <button type="button" className="chip press" onClick={removePhoto}>Delete my photo</button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="press halftone"
              onClick={() => input.current?.click()}
              style={{ height: 180, border: "1.5px dashed var(--sumi)", borderRadius: 12, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, overflow: "hidden", padding: 0 }}
            >
              {preview ? (
                <img src={preview} alt="Your photo" style={{ height: "100%", objectFit: "contain" }} />
              ) : (
                <>
                  <span style={{ fontSize: 28, fontWeight: 700, background: "var(--washi)", border: "var(--line)", borderRadius: 20, width: 40, height: 40, display: "flex", alignItems: "center", justifyContent: "center" }}>+</span>
                  <strong style={{ background: "var(--washi)", padding: "0 6px" }}>Choose a full-body photo</strong>
                  <span className="small" style={{ background: "var(--washi)", padding: "0 6px" }}>Plain background, standing straight.</span>
                </>
              )}
            </button>
          )}
          <input
            ref={input}
            type="file"
            accept="image/*,.heic,.heif"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setFile(f);
                setCheck(null);
                setPreview(/\.(heic|heif)$/i.test(f.name) ? null : URL.createObjectURL(f));
              }
              e.target.value = "";
            }}
          />
          <ul className="small" style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 3 }}>
            <li>Kept only in your closet's private storage. One tap deletes it, along with every render made from it.</li>
            <li>Sent to Meta's Muse Image only to render a look, never to models that train on inputs.</li>
            <li>Location and camera details are stripped before it's saved.</li>
          </ul>
          {file && (
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 14, fontWeight: 700 }}>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--sumi)", flex: "none", marginTop: 1 }} />
              I understand and want to use my photo for try-on.
            </label>
          )}
          {check && (
            <div role="status" className="card" style={{ padding: 10, borderColor: check.ok ? "var(--sumi)" : "var(--shu)" }}>
              <strong style={{ color: check.ok ? "var(--sumi)" : "var(--shu)" }}>{check.ok ? "Looks good." : "Let's retake that one."}</strong>{" "}
              <span className="small">{check.advice}</span>
            </div>
          )}
        </section>
      )}

      {mode === "flat" && (
        <p className="card small" style={{ margin: 0, padding: 12 }}>
          No body at all: looks show as a flat-lay of your real cutouts. Always accurate, nothing about you is used.
        </p>
      )}

      <div style={{ flex: 1 }} />
      <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={busy || !photoReady} onClick={save}>
        {busy ? (mode === "photo" && file ? "Checking your photo…" : "Saving…") : mode === "photo" && file && !consent ? "Tick the box to use your photo" : cta}
      </button>
    </>
  );
}

function Options<T extends string>({ label, values, value, onPick }: { label: string; values: T[]; value: T; onPick: (v: T) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span className="label">{label}</span>
      <div role="radiogroup" aria-label={label} style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
        {values.map((v) => (
          <button key={v} type="button" role="radio" aria-checked={value === v} className="chip press" style={{ height: 30, padding: "0 9px", fontSize: 12 }} onClick={() => onPick(v)}>
            {cap(v)}
          </button>
        ))}
      </div>
    </div>
  );
}

// A live preview: proportions follow build and form, size follows height, colour follows the finish.
function Figure({ body }: { body: BodyProfile }) {
  const w = { slim: 0.82, regular: 1, athletic: 1.12, curvy: 1.08, plus: 1.28 }[body.build];
  const shoulders = (body.silhouette === "masculine" ? 1.12 : body.silhouette === "feminine" ? 0.9 : 1) * w;
  const hips = (body.silhouette === "feminine" || body.build === "curvy" ? 1.16 : 1) * w;
  const s = 0.72 + ((body.height_cm - 140) / 70) * 0.28;
  const fill = TONES[body.skin_tone - 1][0];
  const cx = 50;
  const sh = 22 * shoulders, wa = 15 * w, hi = 20 * hips;
  return (
    <div className="halftone" style={{ flex: "none", width: 104, border: "var(--line)", borderRadius: 10, display: "flex", alignItems: "flex-end", justifyContent: "center", padding: "8px 0" }}>
      <svg viewBox="0 0 100 220" width={92} style={{ height: 210 * s, transition: "height .2s ease" }} aria-label="Mannequin preview" role="img">
        <g fill={fill} stroke="#2B2724" strokeWidth="1.5" strokeLinejoin="round">
          <ellipse cx={cx} cy="18" rx="11" ry="13" />
          <rect x={cx - 4} y="30" width="8" height="8" />
          <path d={`M${cx - sh} 40 Q${cx} 34 ${cx + sh} 40 L${cx + wa} 92 L${cx + hi} 118 L${cx - hi} 118 L${cx - wa} 92 Z`} />
          <path d={`M${cx - sh} 41 L${cx - sh - 7} 104 L${cx - sh - 1} 106 L${cx - sh + 6} 52 Z`} />
          <path d={`M${cx + sh} 41 L${cx + sh + 7} 104 L${cx + sh + 1} 106 L${cx + sh - 6} 52 Z`} />
          <path d={`M${cx - hi} 118 L${cx - 12} 214 L${cx - 3} 214 L${cx} 128 L${cx + 3} 214 L${cx + 12} 214 L${cx + hi} 118 Z`} />
        </g>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------ result

function Result({ job, mode, onSetup, onClose, bare = false }: { job: TryOnJob | null; mode: TryOnMode; onSetup: () => void; onClose: () => void; bare?: boolean }) {
  const [showFlat, setShowFlat] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const running = !job || job.status === "running";

  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    const t = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(t);
  }, [running]);

  const hasRender = !!job?.render_url;
  const src = job ? (hasRender && !showFlat ? job.render_url! : job.flatlay_url) : null;
  const wearer = mode === "photo" ? "On you" : "On the mannequin";

  return (
    <>
      <div className="halftone" style={{ position: "relative", aspectRatio: "3 / 4", border: "var(--line)", borderRadius: 12, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {running ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: 16, textAlign: "center" }}>
            <Oni mood="calm" size={84} />
            <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700, fontSize: 14 }}>
              <span className="spinner-dots">{job?.step ?? "Starting"}</span>
            </span>
            <span className="label" style={{ background: "var(--washi)", padding: "2px 6px" }}>
              MUSE IMAGE + MUSE SPARK · {elapsed}S · USUALLY ABOUT A MINUTE
            </span>
          </div>
        ) : (
          src && <img src={src} alt={hasRender && !showFlat ? `Try-on render: ${job!.look_name}` : `Flat-lay of ${job!.look_name}`} style={{ width: "100%", height: "100%", objectFit: "contain", background: "var(--washi)", animation: "fade .3s ease-out both" }} />
        )}
        {job?.status === "done" && hasRender && job.score !== null && (
          <span className="sticker" style={{ position: "absolute", top: 10, left: 8, fontSize: 11 }}>
            MATCH {job.score}/5
          </span>
        )}
      </div>

      {job?.status === "failed" && (
        <p role="alert" className="small" style={{ margin: 0, color: "var(--shu)", fontWeight: 700 }}>
          {job.error} Here's the flat-lay of your real pieces instead.
        </p>
      )}
      {job?.note && <p className="small muted" style={{ margin: 0 }}>{job.note}</p>}

      {hasRender && (
        <div role="group" aria-label="View" style={{ display: "flex", gap: 6 }}>
          <button type="button" className="chip press" aria-pressed={!showFlat} onClick={() => setShowFlat(false)}>{wearer}</button>
          <button type="button" className="chip press" aria-pressed={showFlat} onClick={() => setShowFlat(true)}>Flat-lay (exact)</button>
        </div>
      )}

      {job?.status === "done" && hasRender && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {job.differences.length > 0 && (
            <>
              <span className="label">WHAT'S SLIGHTLY OFF · THE FLAT-LAY IS EXACT</span>
              <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
                {job.differences.map((d) => <li key={d}>{d}</li>)}
              </ul>
            </>
          )}
          <span className="label muted" style={{ fontWeight: 400, marginTop: 4 }}>
            RENDERED BY MUSE IMAGE · CHECKED BY MUSE SPARK
            {job.cached ? " · CACHED" : ` · ${job.attempts} ${job.attempts === 1 ? "TRY" : "TRIES"} · ${job.seconds}S`}
          </span>
        </div>
      )}

      {!bare && (
        <>
          <div style={{ flex: 1 }} />
          <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
            <button type="button" className="btn press" style={{ flex: 1 }} onClick={onSetup} disabled={running}>
              Who wears it?
            </button>
            <button type="button" className="btn primary press" style={{ flex: 1.3 }} onClick={onClose}>
              Done
            </button>
          </div>
        </>
      )}
    </>
  );
}

// ------------------------------------------------------------------ dress-up (layered)

const LOOK_LETTERS = ["A", "B", "C"];

function DressUp({ plan, initialLook, ctx, onSetup, onClose }: {
  plan: Plan; initialLook: number; ctx: AppCtx; onSetup: () => void; onClose: () => void;
}) {
  const [lookIndex, setLookIndex] = useState(initialLook);
  const [tab, setTab] = useState<"layered" | "exact" | "flat">("layered");
  const [status, setStatus] = useState<LayersStatus | null>(null);
  const [off, setOff] = useState<Set<string>>(new Set());
  const [job, setJob] = useState<TryOnJob | null>(null);
  const [flat, setFlat] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const look = plan.looks[lookIndex];
  // Prepare every look's pieces at once, so switching looks is instant once they're made.
  const allIds = [...new Set(plan.looks.flatMap((l) => l.item_ids))];
  const pending = !!status && (status.base.state === "pending" || status.layers.some((l) => l.state === "pending"));

  useEffect(() => {
    api.tryonLayers(allIds, true).then(setStatus).catch((e) => setError((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan.id]);

  useEffect(() => {
    if (!pending) return;
    const t = setTimeout(() => api.tryonLayers(allIds, false).then(setStatus).catch(() => {}), 2500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    setOff(new Set());
    setJob(null);
    setFlat(null);
  }, [lookIndex]);

  useEffect(() => {
    if (tab === "flat" && !flat) api.flatlay(plan.id, lookIndex).then((r) => setFlat(r.url)).catch(() => {});
    if (tab === "exact" && !job) api.startTryon(plan.id, lookIndex).then(setJob).catch((e) => ctx.toast((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, lookIndex]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setTimeout(() => api.tryonJob(job.id).then(setJob).catch(() => {}), 2000);
    return () => clearTimeout(t);
  }, [job]);

  const byId = new Map(status?.layers.map((l) => [l.item_id, l]) ?? []);
  const pieces = look.items.map((it) => ({ item: it, layer: byId.get(it.id) }));
  const shown = pieces.filter((p) => p.layer?.state === "ready" && !off.has(p.item.id)).sort((a, b) => a.layer!.order - b.layer!.order);
  const making = pieces.filter((p) => p.layer?.state === "pending");
  const [W, H] = status?.base.size ?? [1120, 2240];
  const baseMsg = error ?? (status?.base.state === "failed" ? "Couldn't set up the mannequin." : status?.base.state === "missing" ? "No mannequin made yet." : null);

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <button type="button" className="icon-btn press" aria-label="Previous look" onClick={() => setLookIndex((lookIndex + plan.looks.length - 1) % plan.looks.length)}>
          ◀
        </button>
        <div style={{ textAlign: "center", minWidth: 0 }}>
          <span className="label" style={{ fontWeight: 400 }}>LOOK {LOOK_LETTERS[lookIndex]} · {lookIndex + 1} / {plan.looks.length}</span>
          <h2 className="display" style={{ fontSize: 20, lineHeight: 1.1 }}>{look.name}</h2>
        </div>
        <button type="button" className="icon-btn press" aria-label="Next look" onClick={() => setLookIndex((lookIndex + 1) % plan.looks.length)}>
          ▶
        </button>
      </div>

      <div role="group" aria-label="View" style={{ display: "flex", gap: 6 }}>
        {([["layered", "Dress-up · instant"], ["exact", "Exact render"], ["flat", "Flat-lay"]] as const).map(([id, label]) => (
          <button key={id} type="button" className="chip press" aria-pressed={tab === id} style={{ height: 32, fontSize: 12, padding: "0 10px" }} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "layered" && (
        <>
          <div
            className="halftone"
            style={{ position: "relative", aspectRatio: `${W} / ${H}`, maxHeight: "58dvh", margin: "0 auto", width: "100%", border: "var(--line)", borderRadius: 12, overflow: "hidden" }}
          >
            {status?.base.state === "ready" ? (
              <>
                <img src={status.base.url} alt="Your mannequin" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
                {shown.map(({ item, layer }) => {
                  const [x, y, w, h] = layer!.box!;
                  return (
                    <img
                      key={item.id}
                      src={layer!.url}
                      alt={itemName(item)}
                      style={{
                        position: "absolute", left: `${(x / W) * 100}%`, top: `${(y / H) * 100}%`, width: `${(w / W) * 100}%`, height: `${(h / H) * 100}%`,
                        zIndex: layer!.order, animation: "fade .25s ease-out both",
                      }}
                    />
                  );
                })}
              </>
            ) : (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10, padding: 16, textAlign: "center" }}>
                <Oni mood={baseMsg ? "restless" : "calm"} size={72} />
                <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700, fontSize: 13 }}>
                  {baseMsg ?? <span className="spinner-dots">Setting up your mannequin (just once)</span>}
                </span>
              </div>
            )}
            {making.length > 0 && status?.base.state === "ready" && (
              <span className="label" style={{ position: "absolute", zIndex: 9, left: 8, bottom: 8, right: 8, background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "4px 8px", textAlign: "center" }}>
                <span className="spinner-dots">PUTTING ON {making.map((p) => shortName(p.item).toUpperCase()).join(" + ")}</span>
              </span>
            )}
          </div>

          <div role="group" aria-label="Pieces" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {pieces.map(({ item, layer }) => {
              const on = !off.has(item.id);
              const usable = layer?.state === "ready";
              return (
                <button
                  key={item.id}
                  type="button"
                  className="chip press"
                  aria-pressed={on && usable}
                  disabled={!usable}
                  title={layer?.state === "failed" ? layer.error : layer?.state === "unsupported" ? "Not shown on the mannequin" : undefined}
                  onClick={() => {
                    const next = new Set(off);
                    if (on) next.add(item.id);
                    else next.delete(item.id);
                    setOff(next);
                  }}
                  style={{ height: 32, fontSize: 12, padding: "0 10px" }}
                >
                  {usable ? (on ? "✓ " : "+ ") : ""}{shortName(item)}
                  {layer?.state === "pending" ? " …" : layer?.state === "failed" ? " ✕" : ""}
                </button>
              );
            })}
          </div>
          <span className="small muted">
            {status?.note ?? "Each piece is dressed once, then reused for every outfit. Tap a piece to take it off. Exact render redraws the whole look (about a minute) for tucks and drape."}
          </span>
        </>
      )}

      {tab === "exact" && <Result job={job} mode="mannequin" onSetup={onSetup} onClose={onClose} bare />}

      {tab === "flat" && (
        <div className="halftone" style={{ aspectRatio: "1", border: "var(--line)", borderRadius: 12, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {flat ? <img src={flat} alt={`Flat-lay of ${look.name}`} style={{ width: "100%", height: "100%", objectFit: "contain", background: "var(--washi)" }} /> : <span className="small">Loading…</span>}
        </div>
      )}

      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
        <button type="button" className="btn press" style={{ flex: 1 }} onClick={onSetup}>
          Who wears it?
        </button>
        <button type="button" className="btn primary press" style={{ flex: 1.3 }} onClick={onClose}>
          Done
        </button>
      </div>
    </>
  );
}
