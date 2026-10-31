import { useEffect, useState } from "react";
import { api, shortName, type Item, type QuizPair, type StyleDna } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

// 好み (konomi, "taste"): what the oni has learned about your style, and the this-or-that that teaches it.
// The model behind it is closet/taste.py: it learns from which look you wear, how you rate it, these
// pairs and your corrections, and it says how sure it is.

type Slot = { l: number; t: number; w: number; h: number; z: number };

/**
 * An outfit laid out like a Pinterest collage: a light board, the top over the waistband of the bottoms
 * in a tall left column, and a right-hand column for a layer and any shoes or accessory you own that
 * go with it. Positions are percentages of the board, so it works at any size.
 */
export function OutfitCollage({ items, extras = [] }: { items: Item[]; extras?: Item[] }) {
  const of = (c: string) => items.filter((i) => i.tags?.category === c);
  const [top, bottom, dress, layer] = [of("top")[0], of("bottom")[0], of("dress")[0], of("outerwear")[0]];
  const side = !!layer || extras.length > 0;
  const placed: [Item, Slot][] = [];
  if (dress) placed.push([dress, side ? { l: 2, t: 2, w: 58, h: 96, z: 2 } : { l: 10, t: 2, w: 80, h: 96, z: 2 }]);
  if (bottom) placed.push([bottom, side ? { l: 4, t: 36, w: 56, h: 63, z: 2 } : { l: 16, t: 36, w: 68, h: 63, z: 2 }]);
  if (top) placed.push([top, side ? { l: 0, t: 1, w: 62, h: 40, z: 3 } : { l: 8, t: 1, w: 84, h: 40, z: 3 }]);
  // A layer alone gets the whole right side, draped a little over the top; with extras it shares the column.
  if (layer) placed.push([layer, extras.length ? { l: 55, t: 3, w: 44, h: 38, z: 4 } : { l: 48, t: 14, w: 52, h: 52, z: 4 }]);
  extras.slice(0, 2).forEach((e, n) => placed.push([e, { l: 62, t: (layer ? 46 : 8) + n * 27, w: 34, h: 24, z: 1 }]));
  return (
    <span className="collage" aria-hidden="true">
      {placed.map(([it, s]) => (
        <img
          key={it.id}
          src={it.cutout_url}
          alt=""
          style={{ position: "absolute", left: `${s.l}%`, top: `${s.t}%`, width: `${s.w}%`, height: `${s.h}%`, zIndex: s.z, objectFit: "contain" }}
        />
      ))}
    </span>
  );
}

/** This or that: a few pairs of outfits from your own closet. Tap the one you'd rather wear. */
export function Quiz({ onDone, ctx }: { onDone: (saved: number) => void; ctx: AppCtx }) {
  const [pairs, setPairs] = useState<QuizPair[] | null>(null);
  const [answers, setAnswers] = useState<{ picked: string[]; other: string[] }[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.quiz().then((r) => setPairs(r.pairs)).catch((e) => ctx.toast((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finish = async (all: typeof answers) => {
    setSaving(true);
    try {
      const { saved } = all.length ? await api.answerQuiz(all) : { saved: 0 };
      onDone(saved);
    } catch (e) {
      ctx.toast((e as Error).message);
      setSaving(false);
    }
  };

  if (!pairs) return <p className="small">Picking pairs from your closet…</p>;
  if (!pairs.length) return <p className="small">Scan a few more pieces first: I need at least two outfits to compare.</p>;
  const i = answers.length;
  const pair = pairs[i];
  const pick = (a: Item[], b: Item[]) => {
    const next = [...answers, { picked: a.map((x) => x.id), other: b.map((x) => x.id) }];
    setAnswers(next);
    if (next.length === pairs.length) finish(next);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="label">THIS OR THAT · <span lang="ja">どっち？</span></span>
        <span className="label" style={{ fontWeight: 400 }}>{Math.min(i + 1, pairs.length)} / {pairs.length}</span>
      </div>
      {pair && !saving ? (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, animation: "rise .25s ease-out both" }}>
          {[pair.a, pair.b].map((outfit, n) => (
            <button
              key={n}
              type="button"
              className="press"
              aria-label={`I'd rather wear ${outfit.map(shortName).join(" and ")}`}
              onClick={() => pick(outfit, n ? pair.a : pair.b)}
              style={{ display: "flex", flexDirection: "column", gap: 6, padding: 0, border: 0, background: "transparent", textAlign: "left" }}
            >
              <OutfitCollage items={outfit} extras={n ? pair.b_extras : pair.a_extras} />
              <span className="small" style={{ fontWeight: 700, lineHeight: 1.3 }}>{outfit.map(shortName).join(" + ")}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="small"><span className="spinner-dots">Learning from your picks</span></p>
      )}
      <span className="small muted">Tap the one you'd rather wear. Every answer teaches the oni your taste.</span>
      {!saving && (
        <button type="button" onClick={() => finish(answers)} className="small" style={{ alignSelf: "center", border: 0, background: "none", textDecoration: "underline", color: "inherit", padding: 4 }}>
          {answers.length ? "That's enough for now" : "Skip for now"}
        </button>
      )}
    </div>
  );
}

/** The quiz as a sheet, from Notes ("teach the oni more"). */
export function QuizSheet({ ctx, onClose }: { ctx: AppCtx; onClose: (saved: number) => void }) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="This or that">
      <div className="sheet">
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={() => onClose(0)}>
            ×
          </button>
        </div>
        <Quiz ctx={ctx} onDone={onClose} />
      </div>
    </div>
  );
}

/** Style DNA: the learned taste in plain words, with evidence, this week's change and a "not me". */
export function StyleDnaCard({ ctx }: { ctx: AppCtx }) {
  const [dna, setDna] = useState<StyleDna | null>(null);
  const [quiz, setQuiz] = useState(false);
  const load = () => api.taste().then(setDna).catch(() => {});
  useEffect(() => {
    load();
  }, [ctx.refreshKey, ctx.wardrobeVersion]);
  if (!dna) return null;

  const correct = async (feature: string, value: 1 | -1) => {
    await api.correctTaste(feature, value).catch((e) => ctx.toast((e as Error).message));
    ctx.toast(value > 0 ? "Noted. That's you." : "Noted. I'll stop assuming that.");
    load();
  };

  return (
    <section aria-label="Style DNA" className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
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
      <button type="button" className="btn press" style={{ height: 40, fontSize: 13 }} onClick={() => setQuiz(true)}>
        Teach me more: this or that →
      </button>
      {quiz && (
        <QuizSheet
          ctx={ctx}
          onClose={(saved) => {
            setQuiz(false);
            if (saved) ctx.toast(`Learned from ${saved} pick${saved === 1 ? "" : "s"}.`);
            load();
          }}
        />
      )}
    </section>
  );
}
