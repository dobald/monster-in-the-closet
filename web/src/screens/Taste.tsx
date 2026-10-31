import { useEffect, useState } from "react";
import { api, shortName, type BoardPiece, type Item, type StyleDna, type StyleShare } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

// 好み (konomi, "taste"): what the oni has learned about your style, and the this-or-that that teaches it.
// The model behind it is closet/taste.py: it learns from which look you wear, how you rate it, these
// pairs and your corrections, and it says how sure it is.

type Slot = { l: number; t: number; w: number; h: number; z: number };

export const toPieces = (items: Item[]): BoardPiece[] =>
  items.map((i) => ({ id: i.id, category: i.tags?.category ?? "other", cutout_url: i.photo_url, name: i.tags?.subtype }));

// The right-hand column of a board, top to bottom, and how tall each kind of piece gets (% of the board).
const SIDE: Record<string, number> = { hat: 15, eyewear: 9, jewelry: 12, accessory: 12, bag: 20, shoes: 17 };
const SIDE_ORDER = Object.keys(SIDE);

/**
 * An outfit laid out like a Pinterest board: a light background, the top over the waistband of the
 * bottoms in a tall left column (a layer draped over the top), and a right-hand column of hat, eyewear,
 * jewellery, bag and shoes. Positions are percentages of the board, so it works at any size.
 */
export function OutfitCollage({ pieces }: { pieces: BoardPiece[] }) {
  const of = (c: string) => pieces.filter((p) => p.category === c);
  const [top, bottom, dress, layer] = [of("top")[0], of("bottom")[0], of("dress")[0], of("outerwear")[0]];
  const side = pieces.filter((p) => p.category in SIDE).sort((a, b) => SIDE_ORDER.indexOf(a.category) - SIDE_ORDER.indexOf(b.category)).slice(0, 5);
  const [L, W] = side.length ? [0, 62] : [8, 84];
  const placed: [BoardPiece, Slot][] = [];
  if (dress) placed.push([dress, { l: L + 2, t: 2, w: W - 4, h: 96, z: 2 }]);
  if (bottom) placed.push([bottom, { l: L + W * 0.08, t: 36, w: W * 0.84, h: 63, z: 2 }]);
  if (top && layer) {
    placed.push([layer, { l: L, t: 1, w: W * 0.7, h: 40, z: 3 }]);
    placed.push([top, { l: L + W * 0.42, t: 5, w: W * 0.58, h: 32, z: 2 }]);
  } else if (top || layer) {
    placed.push([(top ?? layer)!, { l: L, t: 1, w: W, h: 40, z: 3 }]);
  }
  const total = side.reduce((n, p) => n + SIDE[p.category], 0) + side.length;
  const scale = Math.min(1, 96 / (total || 1));
  let y = 2;
  side.forEach((p) => {
    const h = SIDE[p.category] * scale;
    placed.push([p, { l: 64, t: y, w: 34, h, z: 4 }]);
    y += h + scale;
  });
  return (
    <span className="collage" aria-hidden="true">
      {placed.map(([p, s]) => (
        <img
          key={p.id}
          src={p.cutout_url}
          alt=""
          loading="lazy"
          style={{ position: "absolute", left: `${s.l}%`, top: `${s.t}%`, width: `${s.w}%`, height: `${s.h}%`, zIndex: s.z, objectFit: "contain" }}
        />
      ))}
    </span>
  );
}

// One side of a pair, whichever quiz it comes from.
type Side = { key: string; pieces: BoardPiece[]; label: string; ids: string[] };

/**
 * This or that. "styles": two Pinterest-style boards from different style worlds, unlabelled so the
 * name doesn't sway the pick ("which is more you?"). "outfits": two outfits from your own closet.
 */
export function Quiz({ kind = "styles", onDone, ctx }: { kind?: "styles" | "outfits"; onDone: (saved: number) => void; ctx: AppCtx }) {
  const [pairs, setPairs] = useState<[Side, Side][] | null>(null);
  const [answers, setAnswers] = useState<[Side, Side][]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load =
      kind === "styles"
        ? api.styleQuiz().then((r) => r.pairs.map((p) => [p.a, p.b].map((b) => ({ key: b.style, pieces: b.pieces, label: b.name, ids: [b.style] })) as [Side, Side]))
        : api.quiz().then((r) =>
            r.pairs.map((p) => [
              { key: p.a.map((i) => i.id).join(), pieces: toPieces([...p.a, ...p.a_extras]), label: p.a.map(shortName).join(" + "), ids: p.a.map((i) => i.id) },
              { key: p.b.map((i) => i.id).join(), pieces: toPieces([...p.b, ...p.b_extras]), label: p.b.map(shortName).join(" + "), ids: p.b.map((i) => i.id) },
            ] as [Side, Side]),
          );
    load.then(setPairs).catch((e) => ctx.toast((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  const finish = async (all: [Side, Side][]) => {
    setSaving(true);
    try {
      let saved = 0;
      if (all.length && kind === "styles") saved = (await api.answerStyleQuiz(all.map(([a, b]) => ({ picked: a.key, other: b.key })))).saved;
      else if (all.length) saved = (await api.answerQuiz(all.map(([a, b]) => ({ picked: a.ids, other: b.ids })))).saved;
      onDone(saved);
    } catch (e) {
      ctx.toast((e as Error).message);
      setSaving(false);
    }
  };

  if (!pairs) return <p className="small">{kind === "styles" ? "Pinning some boards…" : "Picking pairs from your closet…"}</p>;
  if (!pairs.length) {
    return (
      <p className="small">
        {kind === "styles" ? "You've seen every board. Your style mix is in Notes." : "Scan a few more pieces first: I need at least two outfits to compare."}
      </p>
    );
  }
  const i = answers.length;
  const pair = pairs[i];
  const pick = (chosen: Side, other: Side) => {
    const next = [...answers, [chosen, other] as [Side, Side]];
    setAnswers(next);
    if (next.length === pairs.length) finish(next);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="label">{kind === "styles" ? "WHICH IS MORE YOU?" : "THIS OR THAT"} · <span lang="ja">どっち？</span></span>
        <span className="label" style={{ fontWeight: 400 }}>{Math.min(i + 1, pairs.length)} / {pairs.length}</span>
      </div>
      {pair && !saving ? (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, animation: "rise .25s ease-out both" }}>
          {pair.map((side, n) => (
            <button
              key={side.key}
              type="button"
              className="press"
              aria-label={kind === "styles" ? `Board ${n + 1}` : `I'd rather wear ${side.label}`}
              onClick={() => pick(side, pair[1 - n])}
              style={{ display: "flex", flexDirection: "column", gap: 6, padding: 0, border: 0, background: "transparent", textAlign: "left" }}
            >
              <OutfitCollage pieces={side.pieces} />
              {kind === "outfits" && <span className="small" style={{ fontWeight: 700, lineHeight: 1.3 }}>{side.label}</span>}
            </button>
          ))}
        </div>
      ) : (
        <p className="small"><span className="spinner-dots">Learning from your picks</span></p>
      )}
      {i > 0 && kind === "styles" && (
        <span className="small muted">
          Last pick: {answers[i - 1][0].label} over {answers[i - 1][1].label}.
        </span>
      )}
      <span className="small muted">
        {kind === "styles" ? "Go with your gut: the board you'd rather wear. No wrong answers." : "Tap the one you'd rather wear. Every answer teaches the oni your taste."}
      </span>
      {!saving && (
        <button type="button" onClick={() => finish(answers)} className="small" style={{ alignSelf: "center", border: 0, background: "none", textDecoration: "underline", color: "inherit", padding: 4 }}>
          {answers.length ? "That's enough for now" : "Skip for now"}
        </button>
      )}
    </div>
  );
}

/** The quiz as a sheet, from Notes ("teach the oni more"). */
export function QuizSheet({ kind, ctx, onClose }: { kind: "styles" | "outfits"; ctx: AppCtx; onClose: (saved: number) => void }) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="This or that">
      <div className="sheet">
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={() => onClose(0)}>
            ×
          </button>
        </div>
        <Quiz kind={kind} ctx={ctx} onDone={onClose} />
      </div>
    </div>
  );
}

/** Style DNA: the learned taste in plain words, with evidence, this week's change and a "not me".
 * `version` bumps when a quiz round ends, so the card re-reads what was just learned. */
export function StyleDnaCard({ ctx, version, onPlay }: { ctx: AppCtx; version: number; onPlay: (kind: "styles" | "outfits") => void }) {
  const [dna, setDna] = useState<StyleDna | null>(null);
  const load = () => api.taste().then(setDna).catch(() => {});
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.refreshKey, ctx.wardrobeVersion, version]);
  if (!dna) return null;

  const correct = async (feature: string, value: 1 | -1) => {
    await api.correctTaste(feature, value).catch((e) => ctx.toast((e as Error).message));
    ctx.toast(value > 0 ? "Noted. That's you." : "Noted. I'll stop assuming that.");
    load();
  };

  return (
    <section aria-label="Style DNA" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span className="label">STYLE DNA · <span lang="ja">好み</span></span>
        <span className="label" style={{ fontWeight: 400 }}>{dna.signals} SIGNAL{dna.signals === 1 ? "" : "S"}</span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
        <Oni mood="calm" size={44} />
        <p style={{ margin: 0, flex: 1, border: "var(--line)", borderRadius: "12px 12px 12px 2px", padding: "8px 12px", fontSize: 14, lineHeight: 1.45, background: "var(--washi)" }}>
          {dna.narrative}
        </p>
      </div>

      <Styles picture={dna.styles} onPlay={() => onPlay("styles")} />

      {dna.traits.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {dna.traits.map((t) => (
            <li key={t.feature} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <strong style={{ fontSize: 14, lineHeight: 1.35 }}>{t.sentence}</strong>
              <span aria-hidden="true" style={{ height: 6, borderRadius: 3, border: "var(--line)", overflow: "hidden", display: "flex", justifyContent: t.weight > 0 ? "flex-start" : "flex-end" }}>
                <span style={{ width: `${Math.min(100, Math.abs(t.weight) * 40)}%`, background: t.weight > 0 ? "var(--ai)" : "var(--shu)" }} />
              </span>
              <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span className="label muted" style={{ fontWeight: 400, fontSize: 9, flex: 1 }}>FROM {t.evidence} SIGNALS</span>
                <button type="button" className="chip press" style={{ height: 26, fontSize: 11, padding: "0 9px" }} onClick={() => correct(t.feature, t.weight > 0 ? 1 : -1)}>
                  That's me
                </button>
                <button type="button" className="chip press" style={{ height: 26, fontSize: 11, padding: "0 9px" }} onClick={() => correct(t.feature, t.weight > 0 ? -1 : 1)}>
                  Not me
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {dna.week.length > 0 && <span className="small"><strong>This week</strong> you {dna.week.join(", and ")}.</span>}
      {dna.accuracy && (
        <span className="small">
          <strong>How well I know you:</strong> I predicted your pick {dna.accuracy.hits} of {dna.accuracy.n} times (guessing would get{" "}
          {Math.round(dna.accuracy.chance * 100)}%).
        </span>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <span className="small">
          <strong>Outfits explored:</strong> {dna.coverage.worn} of the {dna.coverage.possible} your closet can make
          {dna.stretches_worn ? ` · ${dna.stretches_worn} stretch${dna.stretches_worn === 1 ? "" : "es"} worn` : ""}
        </span>
        <span aria-hidden="true" style={{ height: 8, borderRadius: 4, border: "var(--line)", overflow: "hidden" }}>
          <span style={{ display: "block", height: "100%", width: `${dna.coverage.pct}%`, background: "var(--sumi)" }} />
        </span>
      </div>
      {dna.learning.length > 0 && <span className="small muted">Still learning: {dna.learning.join(", ")}.</span>}
    </section>
  );
}

function Shares({ title, shares, colour, scale }: { title: React.ReactNode; shares: StyleShare[]; colour: string; scale?: number }) {
  const max = scale ?? Math.max(...shares.map((x) => x.pct), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span className="label" style={{ fontSize: 9 }}>{title}</span>
      {shares.map((x) => (
        <span key={x.id} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 2fr 34px", gap: 8, alignItems: "center" }}>
          <span className="small" style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{x.name}</span>
          <span aria-hidden="true" style={{ height: 8, borderRadius: 4, border: "var(--line)", overflow: "hidden" }}>
            <span style={{ display: "block", height: "100%", width: `${(100 * x.pct) / max}%`, background: colour }} />
          </span>
          <span className="label" style={{ fontWeight: 400, textAlign: "right" }}>{x.pct}%</span>
        </span>
      ))}
    </div>
  );
}

// Styles you're drawn to (from the boards), what your closet already says, and where to grow.
function Styles({ picture, onPlay }: { picture: StyleDna["styles"]; onPlay: () => void }) {
  if (!picture.answers) {
    return (
      <button type="button" className="press" onClick={onPlay} style={{ textAlign: "left", border: "1.5px dashed var(--shu)", borderRadius: 10, padding: "10px 12px", background: "transparent" }}>
        <strong style={{ fontSize: 14 }}>Find your styles →</strong>
        <span className="small" style={{ display: "block", marginTop: 2 }}>Pick between Pinterest-style boards: streetwear, dark academia, gothic, soft, minimalist and more.</span>
      </button>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingTop: 2 }}>
      <Shares title={<>STYLES YOU'RE DRAWN TO · <span lang="ja">好きなスタイル</span> · {picture.answers} PICKS</>} shares={picture.liked.filter((x) => x.pct !== 50)} colour="var(--shu)" scale={100} />
      <span className="small muted" style={{ marginTop: -6 }}>How often you'd pick each style's board over an average one. 50% means no opinion yet.</span>
      {picture.closet.length > 0 && <Shares title={<>WHAT YOUR CLOSET SAYS · <span lang="ja">今の服</span></>} shares={picture.closet.slice(0, 3)} colour="var(--ai)" />}
      {picture.grow && (
        <div style={{ border: "1.5px dashed var(--sumi)", borderRadius: 10, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 4 }}>
          <span className="label" style={{ fontSize: 9 }}>ROOM TO GROW · <span lang="ja">{picture.grow.ja}</span></span>
          <strong style={{ fontSize: 14, lineHeight: 1.35 }}>
            You're drawn to {picture.grow.name.toLowerCase()}, but your closet barely says it yet.
          </strong>
          <span className="small">{picture.grow.essence}</span>
          <span className="small">
            <strong>Start with what you own:</strong> {picture.grow.signature.join(", ")}. I'll lean your Stretch looks that way.
          </span>
        </div>
      )}
    </div>
  );
}
