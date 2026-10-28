import { useState } from "react";
import { api, itemName, type Duplicates, type DuplicatePair, type Item } from "../api";
import type { AppCtx } from "../App";

// "Same item?" cards: two cutouts side by side, the oni's reasoning, and the user's call.

export function ReviewPairs({ pairs, ctx, onResolved }: { pairs: DuplicatePair[]; ctx: AppCtx; onResolved: (p: DuplicatePair) => void }) {
  const [busy, setBusy] = useState<string | null>(null);

  const decide = async (p: DuplicatePair, same: boolean) => {
    const key = p.a.id + p.b.id;
    setBusy(key);
    try {
      if (same) {
        const kept = await api.mergeItems(p.a.id, p.b.id);
        ctx.toast(`Merged: ${itemName(kept)} is one item now.`);
      } else {
        await api.notDuplicates(p.a.id, p.b.id);
        ctx.toast("Got it, two different items.");
      }
      onResolved(p);
      ctx.bumpWardrobe();
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!pairs.length) return null;
  return (
    <section aria-label="Possible duplicates" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <span className="label">
        SAME ITEM? · {pairs.length} TO CHECK · <span lang="ja">同じ服？</span>
      </span>
      {pairs.map((p) => {
        const key = p.a.id + p.b.id;
        return (
          <div key={key} className="card" style={{ padding: 10, display: "flex", flexDirection: "column", gap: 10, animation: "rise .3s ease-out both" }}>
            <div style={{ position: "relative", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <Thumb item={p.a} r={-2} />
              <Thumb item={p.b} r={2} />
              <span
                aria-hidden="true"
                className="display"
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "38%",
                  transform: "translate(-50%, -50%) rotate(-8deg)",
                  background: "var(--shu)",
                  color: "#fff",
                  border: "var(--line)",
                  borderRadius: 6,
                  padding: "2px 8px",
                  fontSize: 18,
                }}
              >
                =?
              </span>
            </div>
            <span className="small">
              <strong>{p.checked ? `The oni thinks it's the same (${Math.round((p.confidence ?? 0) * 100)}%): ` : ""}</strong>
              {p.reason}
            </span>
            <div style={{ display: "flex", gap: 8, paddingRight: 3 }}>
              <button type="button" className="btn press" style={{ flex: 1, height: 44 }} disabled={busy === key} onClick={() => decide(p, false)}>
                Different
              </button>
              <button type="button" className="btn primary press" style={{ flex: 1.3, height: 44 }} disabled={busy === key} onClick={() => decide(p, true)}>
                Same item, merge
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}

function Thumb({ item, r }: { item: Item; r: number }) {
  return (
    <span style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="halftone" style={{ display: "block", aspectRatio: "1", border: "var(--line)", borderRadius: 8, padding: 6, transform: `rotate(${r}deg)` }}>
        <img className="cutout" src={item.cutout_url} alt={itemName(item)} />
      </span>
      <span style={{ fontSize: 11, fontWeight: 700, lineHeight: 1.2 }}>{itemName(item)}</span>
      <span className="label" style={{ fontWeight: 400, fontSize: 9 }}>
        {item.source}
      </span>
    </span>
  );
}

export function MergedNote({ dupes }: { dupes: Duplicates }) {
  if (!dupes.merged.length) return null;
  return (
    <div className="card" style={{ padding: "10px 12px", borderStyle: "dashed", display: "flex", gap: 10, alignItems: "center" }}>
      <div style={{ display: "flex", flex: "none" }}>
        {dupes.merged.slice(0, 3).map((m, i) => (
          <span
            key={m.dropped_id}
            className="halftone"
            style={{ width: 40, height: 40, border: "var(--line)", borderRadius: 6, padding: 3, marginLeft: i ? -12 : 0, transform: `rotate(${(i - 1) * 6}deg)` }}
          >
            <img className="cutout" src={m.kept.cutout_url} alt="" />
          </span>
        ))}
      </div>
      <span className="small">
        <strong>
          {dupes.merged.length} already in your closet
        </strong>{" "}
        from another photo, so the oni merged {dupes.merged.length === 1 ? "it" : "them"} instead of adding copies.
      </span>
    </div>
  );
}
