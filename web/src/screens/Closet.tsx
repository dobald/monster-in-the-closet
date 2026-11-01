import { useEffect, useMemo, useState } from "react";
import { api, idleDays, itemName, type DuplicatePair, type Item } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";
import { ReviewPairs } from "./Duplicates";
import { LastWornList } from "./LastWorn";

const FILTERS: { label: string; test: (i: Item) => boolean }[] = [
  { label: "All", test: () => true },
  { label: "Forgotten", test: (i) => idleDays(i) >= 30 },
  { label: "Tops", test: (i) => i.tags?.category === "top" },
  { label: "Bottoms", test: (i) => i.tags?.category === "bottom" },
  { label: "Layers", test: (i) => i.tags?.category === "outerwear" },
  { label: "Dresses", test: (i) => i.tags?.category === "dress" },
  { label: "Shoes", test: (i) => i.tags?.category === "shoes" },
  { label: "Extras", test: (i) => i.tags?.category === "accessory" || i.tags?.category === "other" },
];

export default function Closet({ ctx }: { ctx: AppCtx }) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("All");
  const [q, setQ] = useState("");
  const [checking, setChecking] = useState(false);
  const [review, setReview] = useState<DuplicatePair[]>([]);
  const [history, setHistory] = useState(false);
  // Select mode: tick several pieces (bad scans, things that aren't yours) and remove them in one go.
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const removePicked = async () => {
    if (!picked?.size) return;
    try {
      const ids = [...picked];
      await Promise.all(ids.map((id) => api.deleteItem(id)));
      ctx.toast(`Removed ${ids.length} piece${ids.length === 1 ? "" : "s"}.`, {
        label: "Undo",
        run: () =>
          Promise.all(ids.map((id) => api.restoreItem(id)))
            .then(() => ctx.bumpWardrobe())
            .catch((e) => ctx.toast((e as Error).message)),
      });
      setPicked(null);
      ctx.bumpWardrobe();
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setConfirmRemove(false);
    }
  };

  const removeSample = async () => {
    try {
      const r = await api.removeSample();
      ctx.toast(`Took out the ${r.removed} sample pieces.`);
      ctx.bumpWardrobe();
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  };

  const findDuplicates = async () => {
    setChecking(true);
    try {
      const d = await api.findDuplicates();
      setReview(d.review);
      if (d.merged.length) ctx.bumpWardrobe();
      ctx.toast(
        d.merged.length
          ? `Merged ${d.merged.length} duplicate${d.merged.length === 1 ? "" : "s"}.` + (d.review.length ? ` ${d.review.length} to check.` : "")
          : d.review.length
            ? `${d.review.length} possible duplicate${d.review.length === 1 ? "" : "s"} to check.`
            : "No duplicates. Every item is one of a kind.",
      );
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    api
      .wardrobe()
      .then(setItems)
      .catch((e) => setError((e as Error).message));
  }, [ctx.wardrobeVersion]);

  // Clean product shots are made in the background; refresh the grid as they land.
  useEffect(() => {
    let stop = false;
    let timer: number | undefined;
    let done = -1;
    const poll = (s: { done: number; running: number }) => {
      if (stop) return;
      if (done >= 0 && s.done !== done) api.wardrobe().then((w) => !stop && setItems(w)).catch(() => {});
      done = s.done;
      if (s.running > 0) timer = window.setTimeout(() => api.products().then(poll).catch(() => {}), 4000);
    };
    api.makeProducts().then(poll).catch(() => {});
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [ctx.wardrobeVersion]);

  const shown = useMemo(() => {
    if (!items) return [];
    const f = FILTERS.find((x) => x.label === filter)!;
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return items.filter((i) => {
      if (!f.test(i)) return false;
      if (!words.length) return true;
      const t = i.tags;
      const hay = t ? [t.subtype, t.primary_color, ...t.secondary_colors, t.category, t.material_guess, t.pattern, t.fit, ...t.seasons].join(" ").toLowerCase() : "";
      return words.every((w) => hay.includes(w));
    });
  }, [items, filter, q]);

  const forgotten = items?.filter((i) => idleDays(i) >= 30).length ?? 0;
  const noHistory = items?.filter((i) => !i.last_worn).length ?? 0;
  const present = FILTERS.filter((f) => f.label === "All" || f.label === "Forgotten" || items?.some(f.test));

  return (
    <main className="screen">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "stretch", borderBottom: "var(--line)", paddingBottom: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 60 }}>CLOSET</h1>
          <span style={{ fontSize: 13, fontWeight: 500, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            {items ? `${items.length} items` : "Loading…"}
            {forgotten > 0 && (
              <span style={{ background: "var(--shu)", color: "#fff", borderRadius: 3, padding: "1px 5px", fontWeight: 700 }}>{forgotten} forgotten</span>
            )}
            <button
              type="button"
              className="chip press"
              style={{ height: 28, padding: "0 10px", fontSize: 12 }}
              disabled={checking || !items?.length}
              onClick={findDuplicates}
            >
              {checking ? "Checking…" : "Find duplicates ⧉"}
            </button>
            <button
              type="button"
              className="chip press"
              aria-pressed={!!picked}
              style={{ height: 28, padding: "0 10px", fontSize: 12 }}
              disabled={!items?.length}
              onClick={() => {
                setPicked(picked ? null : new Set());
                setConfirmRemove(false);
              }}
            >
              {picked ? "Done" : "Select"}
            </button>
          </span>
        </div>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 22 }}>
          私の服
        </span>
      </header>

      <label style={{ display: "flex", alignItems: "center", gap: 8, height: 44, padding: "0 14px", border: "var(--line)", borderRadius: 22, background: "var(--washi)" }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="6" />
          <path d="M20 20l-4.5-4.5" />
        </svg>
        <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Search your closet</span>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search: white cotton, jeans, winter…"
          style={{ flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent", fontSize: 14 }}
        />
      </label>

      <div role="group" aria-label="Filter" style={{ display: "flex", gap: 6, overflowX: "auto", padding: "0 3px 5px 0", margin: "0 -16px", paddingLeft: 16, scrollbarWidth: "none" }}>
        {present.map((f) => (
          <button key={f.label} type="button" className="chip press" aria-pressed={filter === f.label} onClick={() => setFilter(f.label)}>
            {f.label}
          </button>
        ))}
        <span style={{ flex: "none", width: 10 }} />
      </div>

      <ReviewPairs pairs={review} ctx={ctx} onResolved={(p) => setReview(review.filter((x) => x !== p))} />

      {items?.some((i) => i.source === "sample closet") && (
        <div className="card" style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10 }}>
          <span className="small" style={{ flex: 1 }}>
            <strong>This is the sample closet.</strong> Scanning your own clothes replaces it, or take it out now.
          </span>
          <button type="button" className="chip press" style={{ flex: "none" }} onClick={removeSample}>Remove sample</button>
        </div>
      )}

      {picked && (
        <div className="card" style={{ position: "sticky", top: 8, zIndex: 5, padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, boxShadow: "3px 3px 0 var(--shu)" }}>
          <span className="small" style={{ flex: 1 }}>
            {picked.size ? `${picked.size} selected` : "Tap the pieces to remove: bad scans, things that aren't yours."}
          </span>
          {confirmRemove ? (
            <>
              <button type="button" className="chip press" onClick={() => setConfirmRemove(false)}>Keep</button>
              <button type="button" className="chip shu press" onClick={removePicked}>Yes, remove</button>
            </>
          ) : (
            <button type="button" className="chip shu press" disabled={!picked.size} onClick={() => setConfirmRemove(true)}>
              Remove {picked.size || ""}
            </button>
          )}
        </div>
      )}

      {items && noHistory >= 2 && noHistory * 3 >= items.length && (
        <button
          type="button"
          className="card press"
          onClick={() => setHistory(true)}
          style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, textAlign: "left", boxShadow: "3px 3px 0 var(--shu)" }}
        >
          <span lang="ja" className="hanko" style={{ width: 40, height: 40, fontSize: 17, flex: "none" }}>思</span>
          <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
            <strong style={{ fontSize: 14 }}>When did you last wear these?</strong>
            <span className="small">{noHistory} pieces have no history yet, so the oni can't tell what's been forgotten.</span>
          </span>
          <span aria-hidden="true" style={{ fontWeight: 700 }}>→</span>
        </button>
      )}
      {history && items && (
        <div className="overlay" role="dialog" aria-modal="true" aria-label="When did you last wear these?" onClick={(e) => e.target === e.currentTarget && setHistory(false)}>
          <div className="sheet">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <button type="button" className="icon-btn press" aria-label="Close" onClick={() => setHistory(false)}>×</button>
              <span className="label" style={{ fontWeight: 400 }}>WEAR HISTORY · <span lang="ja">思い出</span></span>
            </div>
            <h1 className="display" style={{ fontSize: "clamp(30px, 10vw, 40px)", lineHeight: 0.95 }}>WHEN DID YOU LAST WEAR THESE?</h1>
            <span className="small">A rough guess is fine. Guesses never count as wears, and wearing something here always wins.</span>
            <LastWornList
              items={items}
              cta="Save"
              onError={ctx.toast}
              onSaved={(updated) => {
                setHistory(false);
                if (updated.length) {
                  ctx.toast(`Saved ${updated.length} piece${updated.length === 1 ? "" : "s"}. The oni can spot forgotten clothes now.`);
                  ctx.bumpWardrobe();
                }
              }}
            />
          </div>
        </div>
      )}

      {error && <p className="small">{error}</p>}

      {items && items.length === 0 && (
        <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 10, textAlign: "center" }}>
          <Oni mood="starving" size={72} />
          <strong>Nothing in here yet.</strong>
          <button type="button" className="btn shu press block" onClick={() => ctx.go("scan")}>
            Scan my clothes →
          </button>
        </div>
      )}
      {items && items.length > 0 && shown.length === 0 && <p className="small muted">Nothing matches. Try another word.</p>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "14px 10px", paddingBottom: 18 }}>
        {shown.map((it, i) => {
          const idle = idleDays(it);
          // Middle column sits lower: a pinboard rhythm instead of a flat grid.
          const y = i % 3 === 1 ? 18 : 0;
          return (
            <button
              key={it.id}
              type="button"
              aria-pressed={picked ? picked.has(it.id) : undefined}
              onClick={() => {
                if (!picked) return ctx.openItem(it);
                const next = new Set(picked);
                if (next.has(it.id)) next.delete(it.id);
                else next.add(it.id);
                setPicked(next);
                setConfirmRemove(false);
              }}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                padding: 0,
                border: 0,
                background: "transparent",
                textAlign: "left",
                transform: `translateY(${y}px)`,
                animation: `rise .4s ease-out ${Math.min(0.05 * i, 0.6).toFixed(2)}s both`,
              }}
            >
              <span className="halftone" style={{ position: "relative", display: "block", width: "100%", aspectRatio: "1", border: "var(--line)", borderRadius: 8, padding: 6 }}>
                <img className="cutout" src={it.photo_url} alt="" loading="lazy" />
                {picked && (
                  <span
                    aria-hidden="true"
                    style={{
                      position: "absolute", top: 6, right: 6, width: 24, height: 24, borderRadius: 12, border: "var(--line)",
                      display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13,
                      background: picked.has(it.id) ? "var(--shu)" : "var(--washi)", color: picked.has(it.id) ? "#fff" : "transparent",
                    }}
                  >
                    ✓
                  </span>
                )}
                {idle >= 30 && (
                  <span className="sticker" style={{ position: "absolute", top: 6, left: 4, animation: "wobble 3s ease-in-out infinite" }}>
                    {idle}日
                  </span>
                )}
              </span>
              <span className="label" style={{ fontSize: 9, fontWeight: 400 }}>
                品番{String(i + 1).padStart(3, "0")} · {it.wear_count}× WORN
              </span>
              <span style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.2 }}>{itemName(it)} →</span>
            </button>
          );
        })}
      </div>
    </main>
  );
}
