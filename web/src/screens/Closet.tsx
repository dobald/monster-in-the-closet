import { useEffect, useMemo, useState } from "react";
import { api, idleDays, itemName, type Item } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

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

  useEffect(() => {
    api
      .wardrobe()
      .then(setItems)
      .catch((e) => setError((e as Error).message));
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
  const present = FILTERS.filter((f) => f.label === "All" || f.label === "Forgotten" || items?.some(f.test));

  return (
    <main className="screen">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "stretch", borderBottom: "var(--line)", paddingBottom: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 60 }}>CLOSET</h1>
          <span style={{ fontSize: 13, fontWeight: 500 }}>
            {items ? `${items.length} items` : "Loading…"}
            {forgotten > 0 && (
              <>
                {" · "}
                <span style={{ background: "var(--shu)", color: "#fff", borderRadius: 3, padding: "1px 5px", fontWeight: 700 }}>{forgotten} forgotten</span>
              </>
            )}
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

      {error && <p className="small">{error}</p>}

      {items && items.length === 0 && (
        <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 10, textAlign: "center" }}>
          <Oni mood="restless" size={72} />
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
              onClick={() => ctx.openItem(it)}
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
                <img className="cutout" src={it.cutout_url} alt="" loading="lazy" />
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
