import { useEffect, useState } from "react";
import { api, ApiError, itemName, type GapPiece, type Gaps, type ThriftEntry } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

// 古着 (furugi): the gap finder. The few pieces that would unlock the most outfits with what you
// already own, how to spot a good one second-hand, and a list to hunt from.

const SHOPS: { name: string; url: (q: string) => string }[] = [
  { name: "eBay", url: (q) => `https://www.ebay.ca/sch/i.html?_nkw=${encodeURIComponent(q)}` },
  { name: "Depop", url: (q) => `https://www.depop.com/search/?q=${encodeURIComponent(q)}` },
  { name: "Poshmark", url: (q) => `https://poshmark.ca/search?query=${encodeURIComponent(q)}` },
];

// Colour names the model uses that CSS doesn't know.
const SWATCH: Record<string, string> = {
  cream: "#F2E8D5", oatmeal: "#D8CDB8", camel: "#C19A6B", charcoal: "#36454F", toffee: "#A0703C",
  "mid blue": "#5B7DB1", denim: "#4A6A92", rust: "#B7472A", mustard: "#D4A72C", burgundy: "#7A1F2B",
  forest: "#2F4F3A", stone: "#C9C0B0", ecru: "#E9E1CF", "off-white": "#F1ECE2", heather: "#A9A6A3",
};

function swatch(name: string): string {
  const n = name.toLowerCase().trim();
  if (SWATCH[n]) return SWATCH[n];
  for (const w of [n, n.split(" ").at(-1) ?? n, n.replace(/\s+/g, "")]) {
    if (SWATCH[w]) return SWATCH[w];
    if (CSS.supports("color", w)) return w;
  }
  return "var(--paper-3)";
}

export default function Thrift({ ctx }: { ctx: AppCtx }) {
  const [gaps, setGaps] = useState<Gaps | null>(null);
  const [list, setList] = useState<ThriftEntry[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [error, setError] = useState("");

  // Example photos load after the cards: each is one Muse Image call (~25s) the first time.
  const [examples, setExamples] = useState<Record<string, string | null | "loading">>({});
  const fetchExamples = (pieces: GapPiece[]) => {
    for (const p of pieces) {
      if (p.example_url) continue;
      setExamples((e) => ({ ...e, [p.name]: "loading" }));
      api.thriftExample(p)
        .then((r) => setExamples((e) => ({ ...e, [p.name]: r.url })))
        .catch(() => setExamples((e) => ({ ...e, [p.name]: null })));
    }
  };

  const load = async (fresh = false) => {
    setState("loading");
    try {
      const [g, l] = await Promise.all([api.gaps(fresh), api.thrift()]);
      setGaps(g);
      setList(l);
      setState("ready");
      fetchExamples(g.pieces);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setState("empty");
      else {
        setError((e as Error).message);
        setState("error");
      }
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.wardrobeVersion]);

  const exampleFor = (p: GapPiece): string | null | "loading" => p.example_url ?? examples[p.name] ?? null;

  const watch = async (p: GapPiece) => {
    const ex = exampleFor(p);
    await api.addThrift({ ...p, example_url: ex === "loading" ? null : ex }).catch((e) => ctx.toast((e as Error).message));
    setList(await api.thrift());
    ctx.toast(`${p.name} is on your thrift list.`);
  };

  const dismiss = async (p: GapPiece) => {
    await api.addThrift(p, "dismissed").catch((e) => ctx.toast((e as Error).message));
    setGaps((g) => (g ? { ...g, pieces: g.pieces.filter((x) => x.name !== p.name) } : g));
    ctx.toast("Noted. The oni won't suggest it again.");
  };

  const found = async (t: ThriftEntry) => {
    await api.setThrift(t.id, "found");
    setList(await api.thrift());
    ctx.toast(`Found it! Scan your ${t.name.toLowerCase()} to add it to your closet.`);
  };

  const remove = async (t: ThriftEntry) => {
    await api.removeThrift(t.id);
    setList(list.filter((x) => x.id !== t.id));
  };

  const watching = new Set(list.map((t) => t.name.toLowerCase()));
  const hunting = list.filter((t) => t.status === "watching");
  const foundList = list.filter((t) => t.status === "found");

  return (
    <main className="screen">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "stretch", borderBottom: "var(--line)", paddingBottom: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 56 }}>THRIFT</h1>
          <span style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.4, maxWidth: 270 }}>
            The last resort. Only when one piece would unlock lots of new outfits with what you own, and only second-hand.
          </span>
        </div>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 26 }}>
          古着
        </span>
      </header>

      {state === "loading" && (
        <div className="halftone card" style={{ height: 220, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
          <Oni mood="calm" size={64} />
          <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "4px 10px", fontWeight: 700, fontSize: 13 }}>
            <span className="spinner-dots">Sizing up your closet</span>
          </span>
        </div>
      )}
      {state === "empty" && (
        <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 10, textAlign: "center" }}>
          <Oni mood="restless" size={72} />
          <strong>Scan your clothes first, then the oni can spot what's missing.</strong>
          <button type="button" className="btn shu press block" onClick={() => ctx.go("scan")}>
            Scan my clothes →
          </button>
        </div>
      )}
      {state === "error" && (
        <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
          <strong>Couldn't size up the closet.</strong>
          <span className="small">{error}</span>
          <button type="button" className="btn press" onClick={() => load()}>
            Try again →
          </button>
        </div>
      )}

      {state === "ready" && gaps && (
        <>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <Oni mood={ctx.oni?.mood ?? "calm"} size={48} />
            <p
              style={{
                margin: 0,
                flex: 1,
                border: "var(--line)",
                borderRadius: "12px 12px 12px 2px",
                padding: "8px 12px",
                fontSize: 14,
                lineHeight: 1.45,
                background: "var(--washi)",
              }}
            >
              {gaps.summary}
            </p>
          </div>

          {gaps.pieces.map((p, i) => (
            <GapCard
              key={p.name}
              piece={p}
              index={i}
              onList={watching.has(p.name.toLowerCase())}
              onWatch={() => watch(p)}
              onDismiss={() => dismiss(p)}
              example={exampleFor(p)}
              ctx={ctx}
            />
          ))}
          {gaps.pieces.length === 0 && <p className="small muted">No gaps left to suggest. Ask again for fresh ideas.</p>}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="label muted" style={{ fontWeight: 400 }}>
              {gaps.source === "rules" ? "PICKED BY RULES" : "PICKED BY MUSE SPARK OPEN"}
              {gaps.trace.cached ? " · CACHED" : gaps.trace.seconds ? ` · ${gaps.trace.seconds}S` : ""}
            </span>
            <button type="button" className="chip press" onClick={() => load(true)}>
              Ask again ↻
            </button>
          </div>
        </>
      )}

      {(hunting.length > 0 || foundList.length > 0) && (
        <section aria-label="Thrift list" style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
          <hr className="rule" />
          <span className="label">
            THRIFT LIST · {hunting.length} HUNTING{foundList.length ? ` · ${foundList.length} FOUND` : ""} · <span lang="ja">探し中</span>
          </span>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
            {[...hunting, ...foundList].map((t, i) => (
              <Wanted key={t.id} entry={t} tilt={i % 2 ? 1.5 : -1.5} onFound={() => found(t)} onRemove={() => remove(t)} onScan={() => ctx.go("scan")} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function GapCard({ piece: p, index, onList, onWatch, onDismiss, example, ctx }: {
  piece: GapPiece; index: number; onList: boolean; onWatch: () => void; onDismiss: () => void;
  example: string | null | "loading"; ctx: AppCtx;
}) {
  const q = p.search_terms[0] ?? p.name;
  return (
    <article className="card" style={{ position: "relative", padding: 12, display: "flex", flexDirection: "column", gap: 10, animation: `rise .4s ease-out ${index * 0.08}s both` }}>
      {example && (
        <figure
          className="halftone"
          style={{ position: "relative", margin: "-2px -2px 0", border: "var(--line)", borderRadius: 8, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", ...(example === "loading" ? { aspectRatio: "3 / 2" } : {}) }}
        >
          {example === "loading" ? (
            <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "4px 10px", fontWeight: 700, fontSize: 13 }}>
              <span className="spinner-dots">Sketching an example</span>
            </span>
          ) : (
            // A small hint of what to look for, not a product shot: the whole photo, at most 180px tall, whatever its shape.
            <img src={example} alt={`Example of a ${p.name.toLowerCase()}`} style={{ display: "block", maxWidth: "100%", maxHeight: 180, objectFit: "contain", animation: "fade .3s ease-out both" }} />
          )}
          <figcaption className="label" style={{ position: "absolute", left: 8, bottom: 8, background: "var(--washi)", color: "var(--sumi)", border: "var(--line)", borderRadius: 4, padding: "2px 6px", fontSize: 9 }}>
            EXAMPLE · AI-MADE · <span lang="ja">例</span>
          </figcaption>
        </figure>
      )}
      <span
        aria-label={`${p.outfits_unlocked} new outfits`}
        style={{
          position: "absolute",
          top: -12,
          right: 10,
          background: "var(--shu)",
          color: "#fff",
          border: "var(--line)",
          borderRadius: 6,
          padding: "4px 8px 3px",
          transform: "rotate(4deg)",
          textAlign: "center",
          boxShadow: "2px 2px 0 var(--sumi)",
        }}
      >
        <span className="display" style={{ fontSize: 24, display: "block" }}>+{p.outfits_unlocked}</span>
        <span className="label" style={{ fontSize: 8 }}>NEW OUTFITS</span>
      </span>

      <span className="label" style={{ fontWeight: 400 }}>
        GAP {String(index + 1).padStart(2, "0")} · {p.category.toUpperCase()}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 10, paddingRight: 72 }}>
        <span aria-hidden="true" style={{ display: "flex", flex: "none" }}>
          {p.colors.slice(0, 2).map((c, i) => (
            <span key={c} title={c} style={{ width: 26, height: 26, borderRadius: "50%", border: "var(--line)", background: swatch(c), marginLeft: i ? -8 : 0 }} />
          ))}
        </span>
        <h2 className="display" style={{ fontSize: 24, lineHeight: 1.02 }}>{p.name}</h2>
      </div>
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>{p.why}</p>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span className="label" style={{ fontSize: 9 }}>GOES WITH {p.pairs.length} THINGS YOU OWN</span>
        <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 2, scrollbarWidth: "none" }}>
          {p.pairs.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => ctx.openItem(it)}
              aria-label={itemName(it)}
              className="halftone"
              style={{ flex: "none", width: 56, height: 56, border: "var(--line)", borderRadius: 6, padding: 3 }}
            >
              <img className="cutout" src={it.cutout_url} alt="" />
            </button>
          ))}
        </div>
      </div>

      <div style={{ border: "1.5px dashed var(--sumi)", borderRadius: 8, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
          <span className="label">
            WHAT TO LOOK FOR · <span lang="ja">目利き</span>
          </span>
          {p.price_range && <span className="tag-ai">~{p.price_range} USED</span>}
        </span>
        <span style={{ fontSize: 13, lineHeight: 1.5 }}>{p.look_for}</span>
        <span style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span className="label muted" style={{ fontWeight: 400, fontSize: 9 }}>SEARCH “{q.toUpperCase()}” ON</span>
          {SHOPS.map((s) => (
            <a key={s.name} href={s.url(q)} target="_blank" rel="noopener noreferrer" className="chip press" style={{ height: 28, fontSize: 12, padding: "0 10px", display: "inline-flex", alignItems: "center", textDecoration: "none", color: "var(--sumi)" }}>
              {s.name} ↗
            </a>
          ))}
        </span>
      </div>

      <button
        type="button"
        onClick={() => ctx.go("scan")}
        className="small"
        style={{ alignSelf: "flex-start", border: 0, background: "none", padding: 0, textDecoration: "underline", color: "inherit", fontWeight: 700 }}
      >
        Check your closet first: already own one? Scan it in
      </button>
      <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
        <button type="button" className="btn press" style={{ flex: 1, height: 44 }} onClick={onDismiss}>
          Not for me
        </button>
        <button type="button" className="btn primary press" style={{ flex: 1.4, height: 44 }} disabled={onList} onClick={onWatch}>
          {onList ? "On your list ✓" : "Add to thrift list ★"}
        </button>
      </div>
    </article>
  );
}

function Wanted({ entry, tilt, onFound, onRemove, onScan }: { entry: ThriftEntry; tilt: number; onFound: () => void; onRemove: () => void; onScan: () => void }) {
  const p = entry.piece;
  const isFound = entry.status === "found";
  return (
    <div
      className="card"
      style={{ position: "relative", padding: "10px 10px 12px", display: "flex", flexDirection: "column", alignItems: "center", gap: 6, textAlign: "center", transform: `rotate(${tilt}deg)`, background: isFound ? "var(--paper)" : "var(--washi)" }}
    >
      <button
        type="button"
        aria-label={`Remove ${entry.name}`}
        onClick={onRemove}
        style={{ position: "absolute", top: -9, right: -9, width: 26, height: 26, borderRadius: 13, border: "var(--line)", background: "var(--washi)", fontWeight: 700, padding: 0, lineHeight: 1, zIndex: 1 }}
      >
        ×
      </button>
      <span className="display" style={{ fontSize: 16, letterSpacing: "0.04em" }}>
        WANTED <span lang="ja">求む</span>
      </span>
      {p.example_url ? (
        <img src={p.example_url} alt="" style={{ width: "100%", aspectRatio: "1", objectFit: "cover", border: "var(--line)", borderRadius: 6, filter: isFound ? "grayscale(.6)" : undefined }} />
      ) : (
        <span aria-hidden="true" style={{ display: "flex" }}>
          {p.colors.slice(0, 2).map((c, i) => (
            <span key={c} style={{ width: 34, height: 34, borderRadius: "50%", border: "var(--line)", background: swatch(c), marginLeft: i ? -10 : 0 }} />
          ))}
        </span>
      )}
      <strong style={{ fontSize: 13, lineHeight: 1.2 }}>{entry.name}</strong>
      <span className="label" style={{ fontSize: 9 }}>+{p.outfits_unlocked} OUTFITS{p.price_range ? ` · ${p.price_range}` : ""}</span>
      {isFound ? (
        <>
          <span lang="ja" className="hanko" style={{ position: "absolute", top: 34, right: 6, width: 44, height: 44, fontSize: 18 }}>
            済
          </span>
          <button type="button" className="chip press" style={{ height: 30, fontSize: 12 }} onClick={onScan}>
            Scan it in →
          </button>
        </>
      ) : (
        <button type="button" className="chip shu press" style={{ height: 30, fontSize: 12 }} onClick={onFound}>
          Found it!
        </button>
      )}
    </div>
  );
}
