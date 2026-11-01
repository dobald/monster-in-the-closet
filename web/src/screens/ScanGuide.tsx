import { useState } from "react";
import { api, itemName, type Item } from "../api";
import type { AppCtx } from "../App";

// How to scan, shown in setup and on the Scan tab: a do/don't pair of example photos
// (scripts/make_scan_guide.py) and four steps. And the grid of what a scan found, where each piece
// can be opened to fix what it is, or removed if the cutout is bad.

const STEPS: [string, string][] = [
  ["Pick a plain, contrasting spot", "A floor or plain cover that differs from the clothes: light pieces on a darker floor. Busy patterns confuse the cut-out."],
  ["Lay pieces flat, apart", "Up to 8, a hand's width between them. One or two is fine."],
  ["Unfold them", "Sleeves and legs spread out, the print side up."],
  ["Shoot from above", "Phone flat over the pieces, everything in frame, in daylight."],
];

export function ScanGuide() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {(
          [
            ["good", "DO", "Flat, apart, plain floor"],
            ["bad", "DON'T", "A pile, folded, busy cover"],
          ] as const
        ).map(([name, tag, caption]) => (
          <figure key={name} style={{ margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ position: "relative", border: "var(--line)", borderRadius: 8, overflow: "hidden", aspectRatio: "4 / 3", background: "var(--paper)" }}>
              <img src={`/api/scan-guide/${name}.jpg`} alt={caption} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
              <span
                className="label"
                style={{
                  position: "absolute", left: 6, top: 6, fontSize: 10, padding: "2px 6px", borderRadius: 4, border: "var(--line)",
                  background: name === "good" ? "var(--washi)" : "var(--shu)", color: name === "good" ? "var(--sumi)" : "#fff",
                }}
              >
                {name === "good" ? "✓" : "✕"} {tag}
              </span>
            </div>
            <figcaption className="small" style={{ fontSize: 12 }}>{caption}</figcaption>
          </figure>
        ))}
      </div>
      <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
        {STEPS.map(([title, sub], n) => (
          <li key={title} style={{ display: "grid", gridTemplateColumns: "26px 1fr", gap: 8, alignItems: "start" }}>
            <span className="display" aria-hidden="true" style={{ width: 24, height: 24, borderRadius: 12, border: "var(--line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>
              {n + 1}
            </span>
            <span style={{ fontSize: 14, lineHeight: 1.35 }}>
              <strong>{title}.</strong> <span className="small">{sub}</span>
            </span>
          </li>
        ))}
      </ol>
      <span className="small muted" style={{ fontSize: 12 }}>
        Afterwards, tap any piece to fix what it is, or ✕ to remove a bad cut-out.
      </span>
    </div>
  );
}

// The guide behind a "How to scan" toggle: open until the first scan, then folded away (remembered per device).
const SEEN = "monster.scanned";

export function ScanHowTo() {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(SEEN) !== "1";
    } catch {
      return true;
    }
  });
  return (
    <section className="card" style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        style={{ border: 0, background: "transparent", padding: "4px 0", display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: 700, fontSize: 14 }}
      >
        <span>
          How to scan · <span lang="ja" style={{ fontWeight: 500 }}>撮り方</span>
        </span>
        <span aria-hidden="true">{open ? "▴" : "▾"}</span>
      </button>
      {open && <ScanGuide />}
    </section>
  );
}

export function markScanned() {
  try {
    localStorage.setItem(SEEN, "1");
  } catch {
    /* the guide just stays open next time */
  }
}

// A piece the tagger wasn't sure about (or that isn't clothing) gets a "check" badge.
export const needsCheck = (it: Item) => !it.tags || !it.is_garment || it.tags.confidence < 0.7;

export function FoundGrid({ items, ctx, onRemoved, onRestored, columns = 3 }: {
  items: Item[];
  ctx: AppCtx;
  onRemoved: (ids: string[]) => void;
  onRestored: (items: Item[]) => void;
  columns?: number;
}) {
  const [confirm, setConfirm] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string> | null>(null); // select mode

  // Removing is undoable: the pieces are hidden, and "Undo" brings them back.
  const remove = async (gone: Item[]) => {
    try {
      await Promise.all(gone.map((it) => api.deleteItem(it.id)));
      onRemoved(gone.map((it) => it.id));
      ctx.bumpWardrobe();
      ctx.toast(gone.length === 1 ? `Removed ${itemName(gone[0]).toLowerCase()}.` : `Removed ${gone.length} pieces.`, {
        label: "Undo",
        run: () =>
          Promise.all(gone.map((it) => api.restoreItem(it.id)))
            .then((back) => {
              onRestored(back);
              ctx.bumpWardrobe();
            })
            .catch((e) => ctx.toast((e as Error).message)),
      });
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setConfirm(null);
      setPicked(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {items.length > 1 && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
          {picked && (
            <button type="button" className="chip shu press" style={{ height: 28, fontSize: 12 }} disabled={!picked.size}
              onClick={() => remove(items.filter((i) => picked.has(i.id)))}>
              Remove {picked.size || ""}
            </button>
          )}
          <button type="button" className="chip press" aria-pressed={!!picked} style={{ height: 28, fontSize: 12 }}
            onClick={() => setPicked(picked ? null : new Set())}>
            {picked ? "Cancel" : "Select"}
          </button>
        </div>
      )}
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap: 10 }}>
      {items.map((it, i) => (
        <div key={it.id} style={{ position: "relative", display: "flex", flexDirection: "column", gap: 4, animation: `rise .35s ease-out ${(0.06 * i).toFixed(2)}s both` }}>
          <button
            type="button"
            onClick={() => {
              if (!picked) return ctx.openItem(it);
              const next = new Set(picked);
              if (next.has(it.id)) next.delete(it.id);
              else next.add(it.id);
              setPicked(next);
            }}
            aria-pressed={picked ? picked.has(it.id) : undefined}
            aria-label={picked ? `Select ${itemName(it)}` : `${itemName(it)}: open to fix it`}
            style={{ display: "flex", flexDirection: "column", gap: 4, padding: 0, border: 0, background: "transparent", textAlign: "left" }}
          >
            <span className="halftone" style={{ position: "relative", display: "block", width: "100%", aspectRatio: "1", border: "var(--line)", borderRadius: 8, padding: 6 }}>
              <img className="cutout" src={it.photo_url} alt="" />
              {picked && (
                <span aria-hidden="true" style={{
                  position: "absolute", top: 4, left: 4, width: 22, height: 22, borderRadius: 11, border: "var(--line)",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700,
                  background: picked.has(it.id) ? "var(--shu)" : "var(--washi)", color: picked.has(it.id) ? "#fff" : "transparent",
                }}>✓</span>
              )}
              {needsCheck(it) && (
                <span className="label" style={{ position: "absolute", left: 4, bottom: 4, fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "var(--shu)", color: "#fff" }}>
                  CHECK?
                </span>
              )}
            </span>
            <span style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.2 }}>{itemName(it)}</span>
          </button>
          {confirm === it.id ? (
            <div style={{ position: "absolute", inset: "0 0 auto 0", aspectRatio: "1", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, background: "rgba(0,0,0,.55)", borderRadius: 8 }}>
              <button type="button" className="chip shu press" style={{ height: 28, fontSize: 12 }} onClick={() => remove([it])}>Remove</button>
              <button type="button" className="chip press" style={{ height: 28, fontSize: 12 }} onClick={() => setConfirm(null)}>Keep</button>
            </div>
          ) : picked ? null : (
            <button
              type="button"
              aria-label={`Remove ${itemName(it)}`}
              onClick={() => setConfirm(it.id)}
              style={{ position: "absolute", top: 4, right: 4, width: 26, height: 26, borderRadius: 13, border: "var(--line)", background: "var(--washi)", fontSize: 13, fontWeight: 700, padding: 0, lineHeight: 1 }}
            >
              ✕
            </button>
          )}
        </div>
      ))}
    </div>
    </div>
  );
}
