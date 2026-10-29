import { useEffect, useState } from "react";
import { api, type Plan, type Style, type Touch, type Touches as TouchesOut } from "../api";
import type { AppCtx } from "../App";

// 仕上げ (shiage, "finishing"): the small things that make a look. An underlayer peeking out, a
// tuck, pushed sleeves, rings or a belt, from basics the user probably already owns. "I have
// this" adds the basic to their checklist; "Not me" tells the oni to stop suggesting it.

const KIND: Record<Touch["kind"], { ja: string; en: string }> = {
  colour: { ja: "配色", en: "COLOUR" },
  underlayer: { ja: "重ね", en: "LAYER" },
  technique: { ja: "技", en: "TRICK" },
  accessory: { ja: "小物", en: "EXTRA" },
};

export default function Touches({ plan, lookIndex, ctx }: { plan: Plan; lookIndex: number; ctx: AppCtx }) {
  const key = `${plan.id}:${lookIndex}`;
  const [byLook, setByLook] = useState<Record<string, TouchesOut | "loading" | "error">>({});
  const [style, setStyle] = useState<Style | null>(null);
  const [zoom, setZoom] = useState<Touch | null>(null); // the example picture opened full size

  const load = (fresh = false) => {
    if (!fresh && byLook[key]) return;
    setByLook((b) => ({ ...b, [key]: "loading" }));
    api.touches(plan.id, lookIndex)
      .then((r) => setByLook((b) => ({ ...b, [key]: r })))
      .catch(() => setByLook((b) => ({ ...b, [key]: "error" })));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    api.style().then(setStyle).catch(() => {});
  }, []);

  const have = async (t: Touch) => {
    if (!style || !t.needs.length) return;
    const next = await api.updateStyle({ basics: [...new Set([...style.basics, t.needs[0]])] });
    setStyle(next);
    const label = next.catalog.flatMap((g) => g.items).find((i) => i.key === t.needs[0])?.label ?? "it";
    const article = /s$/i.test(label) ? "" : /^[aeiou]/i.test(label) ? "an " : "a "; // "silver rings", "a belt", "an undershirt"
    ctx.toast(`Noted: you have ${article}${label.toLowerCase()}. The oni will lean on it.`);
    setByLook((b) => {
      const cur = b[key] as TouchesOut;
      return { ...b, [key]: { ...cur, touches: cur.touches.map((x) => (x.play === t.play ? { ...x, owned: true, owned_label: label } : x)) } };
    });
  };

  const noneOfThose = async (id: string, name: string) => {
    if (!style) return;
    setStyle(await api.updateStyle({ skip: [...new Set([...style.skip, id])] }));
    ctx.toast(`Noted, no ${name}. If you want one, the Thrift tab finds them second-hand.`);
    setByLook({});
    load(true);
  };

  const notMe = async (t: Touch) => {
    if (!style) return;
    setStyle(await api.updateStyle({ skip: [...new Set([...style.skip, t.play])] }));
    ctx.toast(`Got it. No more "${t.name.toLowerCase()}".`);
    setByLook({});
    load(true);
  };

  const state = byLook[key];
  const ready = state && state !== "loading" && state !== "error" ? state : null;
  return (
    <section aria-label="Finishing touches" style={{ display: "flex", flexDirection: "column", gap: 8, borderTop: "1.5px dashed var(--sumi)", paddingTop: 10 }}>
      {ready && (
        <div aria-label={`Colour read: ${ready.colour.summary}`} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ display: "flex" }} aria-hidden="true">
            {ready.colour.palette.map((p, i) => (
              <span key={p.item_id} title={`${p.name} ${p.hex}`} style={{ width: 22, height: 22, borderRadius: "50%", border: "var(--line)", background: p.hex, marginLeft: i ? -6 : 0 }} />
            ))}
          </span>
          <span style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <strong style={{ fontSize: 13 }}>{ready.colour.plain}</strong>
            {ctx.view === "full" && (
              <span className="label muted" style={{ fontWeight: 400, fontSize: 9 }}>
                <span lang="ja">配色</span> · {ready.colour.summary.toUpperCase()}
              </span>
            )}
          </span>
        </div>
      )}
      <span className="label">
        FINISHING TOUCHES · <span lang="ja">仕上げ</span>
      </span>
      {state === "loading" || state === undefined ? (
        <span className="small muted">
          <span className="spinner-dots">The oni is adding the finishing touches</span>
        </span>
      ) : state === "error" ? (
        <button type="button" className="chip press" style={{ alignSelf: "flex-start" }} onClick={() => load(true)}>
          Couldn't load touches. Try again
        </button>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {state.touches.map((t, i) => (
            <li key={t.play} style={{ display: "grid", gridTemplateColumns: t.example_url ? "72px 1fr" : "40px 1fr", gap: 10, animation: `rise .3s ease-out ${i * 0.08}s both` }}>
              {t.example_url ? (
                <button
                  type="button"
                  className="press"
                  aria-label={`See an example: ${t.name}`}
                  onClick={() => setZoom(t)}
                  style={{ position: "relative", width: 72, height: 72, padding: 0, borderRadius: 8, border: "var(--line)", overflow: "hidden", background: "var(--paper)" }}
                >
                  <img src={t.example_url} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                  <span className="label" style={{ position: "absolute", left: 0, right: 0, bottom: 0, fontSize: 7, padding: "2px 0", background: "var(--washi)", color: "var(--sumi)", borderTop: "var(--line)" }}>
                    {KIND[t.kind].en}
                  </span>
                </button>
              ) : (
                <span
                  aria-hidden="true"
                  style={{
                    width: 40, height: 40, borderRadius: 8, border: "var(--line)", display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", background: t.kind === "underlayer" ? "var(--paper)" : "var(--washi)",
                  }}
                >
                  <span lang="ja" style={{ fontFamily: "var(--display)", fontSize: 13, lineHeight: 1 }}>{KIND[t.kind].ja}</span>
                  <span className="label" style={{ fontSize: 7 }}>{KIND[t.kind].en}</span>
                </span>
              )}
              <span style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
                <strong style={{ fontSize: 14, lineHeight: 1.35 }}>{t.suggestion}</strong>
                <span className="small muted">{t.why}</span>
                <span style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                  {!t.needs.length ? (
                    <span className="label" style={{ fontSize: 9, fontWeight: 400 }}>NO ITEM NEEDED</span>
                  ) : t.owned ? (
                    <span className="label" style={{ fontSize: 9, color: "var(--ai)" }}>YOU HAVE: {t.owned_label?.toUpperCase()} ✓</span>
                  ) : (
                    <>
                      <span className="label" style={{ fontSize: 9, fontWeight: 400 }}>IF YOU HAVE ONE</span>
                      <button type="button" className="chip press" style={{ height: 26, fontSize: 11, padding: "0 9px" }} onClick={() => have(t)}>
                        I have this
                      </button>
                    </>
                  )}
                  <button type="button" className="chip press" style={{ height: 26, fontSize: 11, padding: "0 9px" }} onClick={() => notMe(t)}>
                    Not me
                  </button>
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {zoom?.example_url && <ExampleSheet touch={zoom} onClose={() => setZoom(null)} />}
      {ready?.recall && (
        <div
          style={{
            marginTop: 4, display: "flex", flexDirection: "column", gap: 8, padding: "10px 12px", borderRadius: 10,
            border: "1.5px dashed var(--shu)", background: "var(--washi)", animation: "rise .3s ease-out .25s both",
          }}
        >
          <span className="label" style={{ color: "var(--shu)" }}>
            GOT ONE? · <span lang="ja">探して</span>
          </span>
          <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.4 }}>{ready.recall.text}</span>
          <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button type="button" className="chip shu press" style={{ height: 30, fontSize: 12 }} onClick={() => ctx.go("scan")}>
              Scan it in →
            </button>
            <button type="button" className="chip press" style={{ height: 30, fontSize: 12 }} onClick={() => noneOfThose(ready.recall!.id, ready.recall!.name)}>
              I don't have one
            </button>
          </span>
        </div>
      )}
    </section>
  );
}

// The example picture full size: what the idea looks like, clearly marked as an AI example.
function ExampleSheet({ touch, onClose }: { touch: Touch; onClose: () => void }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={`Example: ${touch.name}`} onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} style={{ gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="label">
            {KIND[touch.kind].en} · <span lang="ja">{KIND[touch.kind].ja}</span>
          </span>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        <figure style={{ margin: 0, position: "relative", border: "var(--line)", borderRadius: 10, overflow: "hidden", background: "var(--paper)" }}>
          <img src={touch.example_url!} alt={`Example of ${touch.name.toLowerCase()}`} style={{ width: "100%", display: "block" }} />
          <figcaption className="label" style={{ position: "absolute", left: 8, bottom: 8, background: "var(--washi)", color: "var(--sumi)", border: "var(--line)", borderRadius: 4, padding: "2px 6px", fontSize: 9 }}>
            EXAMPLE · AI-MADE · <span lang="ja">例</span>
          </figcaption>
        </figure>
        <strong style={{ fontSize: 17 }}>{touch.name}</strong>
        <span style={{ fontSize: 14, lineHeight: 1.5 }}>{touch.suggestion}</span>
        <span className="small muted">{touch.why}</span>
      </div>
    </div>
  );
}

/** Notes: the checklist of basics people own but rarely scan. */
export function BasicsChecklist({ ctx }: { ctx: AppCtx }) {
  const [style, setStyle] = useState<Style | null>(null);
  useEffect(() => {
    api.style().then(setStyle).catch(() => {});
  }, []);
  if (!style) return null;

  const toggle = async (k: string) => {
    const on = style.basics.includes(k);
    try {
      setStyle(await api.updateStyle({ basics: on ? style.basics.filter((b) => b !== k) : [...style.basics, k] }));
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  };

  return (
    <section aria-label="Things you own but don't scan" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span className="label">THINGS YOU OWN BUT DON'T SCAN · <span lang="ja">小物</span></span>
      <span className="small muted">Tick what you have, so finishing touches use your own basics first.</span>
      {style.catalog.map((g) => (
        <div key={g.group} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="label" style={{ fontWeight: 400, fontSize: 9 }}>{g.group.toUpperCase()}</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {g.items.map((it) => (
              <button key={it.key} type="button" className="chip press" aria-pressed={style.basics.includes(it.key)} style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={() => toggle(it.key)}>
                {it.label}
                {style.basics.includes(it.key) ? " ✓" : ""}
              </button>
            ))}
          </div>
        </div>
      ))}
      {style.skip.length > 0 && (
        <button type="button" className="chip press" style={{ alignSelf: "flex-start", height: 30, fontSize: 12 }} onClick={async () => setStyle(await api.updateStyle({ skip: [] }))}>
          Bring back {style.skip.length} skipped touch{style.skip.length === 1 ? "" : "es"}
        </button>
      )}
    </section>
  );
}
