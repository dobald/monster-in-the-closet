import { useState } from "react";
import { api, idleDays, itemName, type Item } from "../api";
import type { AppCtx } from "../App";
import { bucketFor, LastWornSelect } from "./LastWorn";

// Item detail (wireframe 3a, trimmed): the cutout, its tags and wear history, and a remove action.

export default function ItemSheet({ item, ctx, onClose }: { item: Item; ctx: AppCtx; onClose: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [current, setCurrent] = useState(item);
  const t = item.tags;
  const idle = idleDays(current);

  const remove = async () => {
    try {
      await api.deleteItem(item.id);
      ctx.toast(`${itemName(item)} removed from your closet.`);
      ctx.bumpWardrobe();
      onClose();
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  };

  const rows: [string, string][] = t
    ? [
        ["Category", t.category],
        ["Colour", [t.primary_color, ...t.secondary_colors].join(", ")],
        ["Fit", t.fit],
        ["Material", t.material_guess],
        ["Pattern", t.pattern],
        ["Formality", t.formality.replace("_", " ")],
        ["Seasons", t.seasons.join(", ")],
        ["Details", t.distinctive_details],
      ]
    : [];

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={itemName(item)} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            {(t?.category ?? "ITEM").toUpperCase()} · {item.wear_count}× WORN
          </span>
        </div>

        <div className="halftone" style={{ position: "relative", height: 300, border: "var(--line)", borderRadius: 12, padding: 18 }}>
          <img className="cutout" src={item.cutout_url} alt={itemName(item)} />
          {idle >= 30 && (
            <span className="sticker" style={{ position: "absolute", top: 12, left: 10, fontSize: 12 }}>
              {idle}日 UNWORN
            </span>
          )}
        </div>

        <h1 className="display" style={{ fontSize: 30, lineHeight: 1.05 }}>{itemName(item)}</h1>
        <span className="small">
          {current.last_worn
            ? `${current.worn_estimated ? "Last worn around" : "Last worn"} ${new Date(current.last_worn + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
            : "No wear history yet"}
          {" · from "}
          {item.source}
        </span>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="label" style={{ width: 80 }}>LAST WORN</span>
          <LastWornSelect
            item={current}
            value={bucketFor(current)}
            onChange={async (days) => {
              try {
                const [updated] = await api.setLastWorn([{ id: current.id, days_ago: days }]);
                setCurrent(updated);
                ctx.bumpWardrobe();
              } catch (e) {
                ctx.toast((e as Error).message);
              }
            }}
          />
        </div>

        {t && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="label" style={{ width: 80 }}>WARMTH</span>
              <div role="img" aria-label={`Warmth ${t.warmth} of 5`} style={{ display: "flex", gap: 4, flex: 1 }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <span key={n} style={{ flex: 1, height: 10, borderRadius: 2, ...(n <= t.warmth ? { background: "var(--shu)" } : { border: "var(--line)" }) }} />
                ))}
              </div>
            </div>
            <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "80px 1fr", gap: "8px 10px", borderTop: "var(--line)", paddingTop: 10 }}>
              {rows.map(([k, v]) => (
                <div key={k} style={{ display: "contents" }}>
                  <dt className="label" style={{ paddingTop: 2 }}>{k}</dt>
                  <dd style={{ margin: 0, fontSize: 14, lineHeight: 1.4 }}>{v}</dd>
                </div>
              ))}
            </dl>
          </>
        )}

        <div style={{ flex: 1 }} />
        {confirming ? (
          <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
            <button type="button" className="btn press" style={{ flex: 1 }} onClick={() => setConfirming(false)}>
              Keep it
            </button>
            <button type="button" className="btn shu press" style={{ flex: 1 }} onClick={remove}>
              Yes, remove
            </button>
          </div>
        ) : (
          <button type="button" className="btn press block" onClick={() => setConfirming(true)}>
            Not mine / remove from closet
          </button>
        )}
      </div>
    </div>
  );
}
