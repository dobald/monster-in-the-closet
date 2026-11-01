import { useEffect, useRef, useState } from "react";
import { api, type Scan as ScanResult } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";
import { MergedNote, ReviewPairs } from "./Duplicates";
import { FoundGrid, markScanned, needsCheck, ScanHowTo } from "./ScanGuide";

// Flat-lay scan (wireframe 1a/1b): take or choose 1-10 photos of up to 8 items each (one is fine), send them as one
// batch, then show the cutouts the oni found, each one fixable or removable on the spot.

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
  const camera = useRef<HTMLInputElement>(null);

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
      markScanned();
      ctx.bumpWardrobe();
      if (r.sample_removed) ctx.toast(`Your own clothes are in, so I took out the ${r.sample_removed} sample pieces.`);
      // Pre-dress the mannequin with the new pieces in the background, so try-on is instant later.
      api.tryonProfile()
        .then((p) => {
          if (p.mode === "mannequin" && p.ready) api.tryonLayers(r.items.map((i) => i.id), true).catch(() => {});
        })
        .catch(() => {});
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

      {!busy && <ScanHowTo />}

      <div
        style={{
          position: "relative",
          height: shots.length || busy ? 330 : 150,
          border: "var(--line)",
          borderRadius: 12,
          overflow: "hidden",
          backgroundColor: "var(--cam)",
          backgroundImage: "radial-gradient(var(--cam-dot) 1px, transparent 1.6px)",
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
            Your photos show up here. Take one now, or choose some from your phone.
          </p>
        )}
      </div>


      {ctx.health?.mode === "fixture" && (
        <p className="small" style={{ margin: 0, padding: "8px 10px", border: "1.5px dashed var(--shu)", borderRadius: 8 }}>
          <strong>Demo mode.</strong> Scans here replay a recorded closet instead of reading your photo. Start the server in live
          mode to scan your own clothes.
        </p>
      )}

      {error && (
        <p role="alert" className="small" style={{ margin: 0, color: "var(--shu)", fontWeight: 700 }}>
          {error}
        </p>
      )}

      {[input, camera].map((ref, n) => (
        <input
          key={n}
          ref={ref}
          type="file"
          accept="image/*,.heic,.heif"
          multiple={n === 0}
          capture={n === 1 ? "environment" : undefined}
          hidden
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      ))}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, paddingRight: 3, marginTop: 4 }}>
        <button type="button" className="btn shu press" style={{ height: 52 }} disabled={busy || shots.length >= MAX} onClick={() => camera.current?.click()}>
          Take a photo
        </button>
        <button type="button" className="btn press" style={{ height: 52 }} disabled={busy || shots.length >= MAX} onClick={() => input.current?.click()}>
          Choose photos
        </button>
      </div>
      {shots.length > 0 && (
        <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={busy} onClick={build}>
          {busy ? "Scanning…" : `Scan ${shots.length} photo${shots.length === 1 ? "" : "s"} →`}
        </button>
      )}
      <span className="small">Photos go to Meta only to find your clothes. We keep just the cutouts.</span>
    </main>
  );
}

function ScanDone({ result, again, ctx }: { result: ScanResult; again: () => void; ctx: AppCtx }) {
  const [review, setReview] = useState(result.duplicates?.review ?? []);
  const [items, setItems] = useState(result.items);
  const unsure = items.filter(needsCheck).length;
  return (
    <main className="screen">
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Oni mood="fed" size={70} />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 36 }}>{result.replayed ? "DEMO SCAN" : `FOUND ${items.length}!`}</h1>
          <span className="label" style={{ fontWeight: 400 }}>
            {result.photos} PHOTO{result.photos === 1 ? "" : "S"} · {result.seconds.toFixed(1)}S{result.replayed ? " · DEMO REPLAY" : ""}
            {result.cached_photos ? ` · ${result.cached_photos} CACHED` : ""}
          </span>
        </div>
      </header>

      {result.replayed && (
        <p className="small" style={{ margin: 0, padding: "8px 10px", border: "1.5px dashed var(--shu)", borderRadius: 8 }}>
          Demo mode: your photo wasn't sent to the models, so this is a recorded scan, not your clothes. Start the server in live mode to scan for real.
        </p>
      )}
      {result.duplicates && <MergedNote dupes={result.duplicates} />}
      <ReviewPairs pairs={review} ctx={ctx} onResolved={(p) => setReview(review.filter((x) => x !== p))} />

      {!!result.sample_removed && (
        <span className="small">Your own clothes are in, so the {result.sample_removed} sample pieces are gone.</span>
      )}
      <p className="small" style={{ margin: 0 }}>
        <strong>Check what I found.</strong> Tap a piece to fix what it is; ✕ removes a bad cut-out.
        {unsure > 0 && <> I'm unsure about {unsure}: they're marked <strong style={{ color: "var(--shu)" }}>CHECK?</strong></>}
      </p>
      {result.warnings?.map((w) => (
        <p key={w} className="small" style={{ margin: 0, padding: "8px 10px", border: "1.5px dashed var(--shu)", borderRadius: 8 }}>{w}</p>
      ))}
      <FoundGrid
        items={items}
        ctx={ctx}
        onRemoved={(ids) => setItems((now) => now.filter((i) => !ids.includes(i.id)))}
        onRestored={(back) => setItems((now) => [...now, ...back.filter((b) => !now.some((i) => i.id === b.id))])}
      />

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
