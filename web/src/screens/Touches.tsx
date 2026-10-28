import { useEffect, useState } from "react";
import { api, type Plan, type Style, type Touch } from "../api";
import type { AppCtx } from "../App";

// 仕上げ (shiage, "finishing"): the small things that make a look. An underlayer peeking out, a
// tuck, pushed sleeves, rings or a belt, from basics the user probably already owns. "I have
// this" adds the basic to their checklist; "Not me" tells the oni to stop suggesting it.

const KIND: Record<Touch["kind"], { ja: string; en: string }> = {
  underlayer: { ja: "重ね", en: "LAYER" },
  technique: { ja: "技", en: "TRICK" },
  accessory: { ja: "小物", en: "EXTRA" },
};

export default function Touches({ plan, lookIndex, ctx }: { plan: Plan; lookIndex: number; ctx: AppCtx }) {
  const key = `${plan.id}:${lookIndex}`;
  const [byLook, setByLook] = useState<Record<string, Touch[] | "loading" | "error">>({});
  const [style, setStyle] = useState<Style | null>(null);

  const load = (fresh = false) => {
    if (!fresh && byLook[key]) return;
    setByLook((b) => ({ ...b, [key]: "loading" }));
    api.touches(plan.id, lookIndex)
      .then((r) => setByLook((b) => ({ ...b, [key]: r.touches })))
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
    ctx.toast(`Noted: you have ${label.toLowerCase()}. The oni will lean on it.`);
    setByLook((b) => ({ ...b, [key]: (b[key] as Touch[]).map((x) => (x.play === t.play ? { ...x, owned: true, owned_label: label } : x)) }));
  };

  const notMe = async (t: Touch) => {
    if (!style) return;
    setStyle(await api.updateStyle({ skip: [...new Set([...style.skip, t.play])] }));
    ctx.toast(`Got it. No more "${t.name.toLowerCase()}".`);
    setByLook({});
    load(true);
  };

  const state = byLook[key];
  return (
    <section aria-label="Finishing touches" style={{ display: "flex", flexDirection: "column", gap: 8, borderTop: "1.5px dashed var(--sumi)", paddingTop: 10 }}>
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
          {state.map((t, i) => (
            <li key={t.play} style={{ display: "grid", gridTemplateColumns: "40px 1fr", gap: 10, animation: `rise .3s ease-out ${i * 0.08}s both` }}>
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
    </section>
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
