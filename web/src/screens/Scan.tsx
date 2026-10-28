import { useEffect, useRef, useState } from "react";
import { api, itemName, type Scan as ScanResult } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";
import { MergedNote, ReviewPairs } from "./Duplicates";

// Flat-lay scan (wireframe 1a/1b): pick or shoot 1-10 photos of 4-8 items each, send them as one batch,
// then show the cutouts the oni found.

const MAX = 10;

interface Shot {
  file: File;
  url: string | null; // null when the browser can't preview it (HEIC)
}

export default function Scan({ ctx }: { ctx: AppCtx }) {
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => () => shots.forEach((s) => s.url && URL.revokeObjectURL(s.url)), [shots]);

  const add = (files: FileList | null) => {
    if (!files) return;
    const next = Array.from(files)
      .slice(0, MAX - shots.length)
      .map((file) => ({ file, url: /\.(heic|heif)$/i.test(file.name) ? null : URL.createObjectURL(file) }));
    setShots([...shots, ...next]);
    setError(null);
  };

  const build = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.scan(shots.map((s) => s.file));
      setResult(r);
      setShots([]);
      ctx.bumpWardrobe();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (result) return <ScanDone result={result} again={() => setResult(null)} ctx={ctx} />;

  return (
    <main className="screen" style={{ gap: 10 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 56 }}>SCAN</h1>
          <span className="label" style={{ fontWeight: 400 }}>
            BATCH OF {shots.length} / {MAX} PHOTOS · <span lang="ja">撮影</span>
          </span>
        </div>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 22 }}>
          撮る
        </span>
      </header>

      <div
        style={{
          position: "relative",
          height: 330,
          border: "var(--line)",
          borderRadius: 12,
          overflow: "hidden",
          backgroundColor: "#CFC6B8",
          backgroundImage: "radial-gradient(#9A8F80 1px, transparent 1.6px)",
          backgroundSize: "6px 6px",
        }}
      >
        <div
          aria-hidden="true"
          style={{ position: "absolute", inset: 16, borderRadius: 10, border: "2px dashed var(--washi)" }}
        />
        {busy ? (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <Oni mood="calm" size={84} />
            <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700, fontSize: 14 }}>
              <span className="spinner-dots">Finding your clothes</span>
            </span>
            {ctx.health?.mode === "live" && (
              <span className="label" style={{ background: "var(--washi)", padding: "2px 6px" }}>
                SAM 3.1 + MUSE SPARK · ~30–60S
              </span>
            )}
          </div>
        ) : shots.length ? (
          <div style={{ position: "absolute", inset: 26, display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, alignContent: "start", overflowY: "auto" }}>
            {shots.map((s, i) => (
              <span
                key={i}
                style={{
                  position: "relative",
                  aspectRatio: "1",
                  border: "var(--line)",
                  borderRadius: 6,
                  overflow: "hidden",
                  background: "var(--paper)",
                  animation: "rise .3s ease-out both",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {s.url ? (
                  <img src={s.url} alt={s.file.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <span className="label" style={{ textAlign: "center" }}>HEIC<br />{i + 1}</span>
                )}
                <button
                  type="button"
                  aria-label={`Remove photo ${i + 1}`}
                  onClick={() => setShots(shots.filter((_, j) => j !== i))}
                  style={{ position: "absolute", top: 3, right: 3, width: 22, height: 22, borderRadius: 11, border: "var(--line)", background: "var(--washi)", fontSize: 12, fontWeight: 700, padding: 0, lineHeight: 1 }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p style={{ position: "absolute", left: 30, right: 30, top: 34, margin: 0, padding: "8px 10px", borderRadius: 8, background: "var(--washi)", border: "var(--line)", fontSize: 14, fontWeight: 700, lineHeight: 1.35, textAlign: "center" }}>
            Lay 4–8 items flat and take a photo. Spread them out so they don't overlap. Repeat for more batches.
          </p>
        )}
      </div>

      <div role="group" aria-label="Tips" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {["Bed or floor", "No overlaps", "Print side up", "Good light"].map((t) => (
          <span key={t} style={{ fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 12, border: "var(--line)" }}>
            {t}
          </span>
        ))}
      </div>

      {error && (
        <p role="alert" className="small" style={{ margin: 0, color: "var(--shu)", fontWeight: 700 }}>
          {error}
        </p>
      )}

      <input
        ref={input}
        type="file"
        accept="image/*,.heic,.heif"
        multiple
        hidden
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      <div style={{ display: "flex", gap: 12, alignItems: "center", paddingRight: 3, marginTop: 4 }}>
        <button
          type="button"
          className="press"
          aria-label="Add photos"
          disabled={busy || shots.length >= MAX}
          onClick={() => input.current?.click()}
          style={{ flex: "none", width: 66, height: 66, borderRadius: "50%", border: "var(--line)", background: "var(--shu)", boxShadow: "3px 3px 0 var(--sumi)", display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <span aria-hidden="true" style={{ width: 26, height: 26, borderRadius: "50%", border: "3px solid #fff" }} />
        </button>
        <button type="button" className="btn primary press" style={{ flex: 1, height: 52 }} disabled={busy || !shots.length} onClick={build}>
          {busy ? "Scanning…" : shots.length ? `Build my closet (${shots.length}) →` : "Add a photo first"}
        </button>
      </div>
      <span className="small">Photos go to Meta only to find your clothes. We keep just the cutouts.</span>
    </main>
  );
}

function ScanDone({ result, again, ctx }: { result: ScanResult; again: () => void; ctx: AppCtx }) {
  const [review, setReview] = useState(result.duplicates?.review ?? []);
  return (
    <main className="screen">
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Oni mood="fed" size={70} />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 36 }}>FOUND {result.items.length}!</h1>
          <span className="label" style={{ fontWeight: 400 }}>
            {result.photos} PHOTO{result.photos === 1 ? "" : "S"} · {result.seconds.toFixed(1)}S{result.replayed ? " · DEMO REPLAY" : ""}
            {result.cached_photos ? ` · ${result.cached_photos} CACHED` : ""}
          </span>
        </div>
      </header>

      {result.duplicates && <MergedNote dupes={result.duplicates} />}
      <ReviewPairs pairs={review} ctx={ctx} onResolved={(p) => setReview(review.filter((x) => x !== p))} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
        {result.items.map((it, i) => (
          <button
            key={it.id}
            type="button"
            onClick={() => ctx.openItem(it)}
            style={{ display: "flex", flexDirection: "column", gap: 4, padding: 0, border: 0, background: "transparent", textAlign: "left", animation: `rise .35s ease-out ${(0.06 * i).toFixed(2)}s both` }}
          >
            <span className="halftone" style={{ display: "block", aspectRatio: "1", border: "var(--line)", borderRadius: 8, padding: 6 }}>
              <img className="cutout" src={it.cutout_url} alt="" />
            </span>
            <span style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.2 }}>{itemName(it)}</span>
          </button>
        ))}
      </div>

      {result.dropped.length > 0 && (
        <span className="small muted">
          Skipped {result.dropped.length} bit{result.dropped.length === 1 ? "" : "s"} that weren't clothes or were too small.
        </span>
      )}

      <div style={{ display: "flex", gap: 10, paddingRight: 3, marginTop: 6 }}>
        <button type="button" className="btn press" style={{ flex: 1 }} onClick={again}>
          Scan more
        </button>
        <button type="button" className="btn primary press" style={{ flex: 1.4 }} onClick={() => ctx.go("closet")}>
          See my closet →
        </button>
      </div>
    </main>
  );
}
