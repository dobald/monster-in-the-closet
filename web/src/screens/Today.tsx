import { useEffect, useState } from "react";
import { api, ApiError, idleDays, itemName, shortName, type Item, type Look, type Plan, type WeatherPart } from "../api";
import type { AppCtx } from "../App";
import Oni, { MOOD_LABEL } from "../Oni";
import TraceSheet from "./Trace";
import Touches from "./Touches";

const WEEKDAY_JA = ["日曜日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日"];
const LOOK_LETTERS = ["A", "B", "C"];

// The adjust chips become plain-language notes for the planner.
const ADJUST: { label: string; note: string }[] = [
  { label: "Warmer", note: "warmer than usual" },
  { label: "Dressier", note: "dress it up a bit" },
  { label: "No black", note: "nothing black" },
];

type Load = { state: "loading" | "thinking" } | { state: "empty"; msg: string } | { state: "error"; msg: string } | { state: "ready" };

export default function Today({ ctx }: { ctx: AppCtx }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [lookIndex, setLookIndex] = useState(0);
  const [adjust, setAdjust] = useState<Record<string, boolean>>({});
  const [wearing, setWearing] = useState(false);
  const [wornLook, setWornLook] = useState<number | null>(null);
  const [showTrace, setShowTrace] = useState(false);
  const [more, setMore] = useState(false); // simple view: the folded extras for this visit
  const full = ctx.view === "full";
  const open = full || more;

  const replan = async (notes: string, fresh = false) => {
    setLoad({ state: "thinking" });
    try {
      const p = await api.makePlan(notes, fresh);
      setPlan(p);
      setLookIndex(0);
      setLoad({ state: "ready" });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setLoad({ state: "empty", msg: e.message });
      else setLoad({ state: "error", msg: (e as Error).message });
    }
  };

  useEffect(() => {
    api
      .latestPlan()
      .then((p) => {
        setPlan(p);
        setAdjust(Object.fromEntries(ADJUST.map((a) => [a.label, p.notes.includes(a.note)])));
        setLoad({ state: "ready" });
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) replan("");
        else setLoad({ state: "error", msg: (e as Error).message });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.wardrobeVersion]);

  const toggle = (label: string) => {
    const next = { ...adjust, [label]: !adjust[label] };
    setAdjust(next);
    replan(ADJUST.filter((a) => next[a.label]).map((a) => a.note).join(", "));
  };

  const wear = async () => {
    if (!plan) return;
    setWearing(true);
    try {
      const result = await api.wear(plan.id, lookIndex);
      setWornLook(lookIndex);
      ctx.showWorn(result, plan, lookIndex);
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setWearing(false);
    }
  };

  const now = new Date();
  const look = plan?.looks[lookIndex];
  const mood = ctx.oni?.mood ?? "calm";

  return (
    <main className="screen" style={{ gap: 10 }}>
      <span
        aria-hidden="true"
        className="display"
        style={{
          position: "absolute",
          right: -14,
          top: 8,
          fontSize: 190,
          color: "transparent",
          WebkitTextStroke: "1.5px var(--ghost)",
          pointerEvents: "none",
        }}
      >
        {now.getDate()}
      </span>

      <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="label" style={{ fontWeight: 400 }}>
          MONSTER IN THE CLOSET · <span lang="ja">東京</span>
        </span>
        {ctx.health?.mode === "fixture" && (
          <span className="label" title="No paid model calls: plans come from the rule picker" style={{ border: "var(--line)", borderRadius: 4, padding: "2px 6px" }}>
            DEMO DATA
          </span>
        )}
      </div>

      <header style={{ position: "relative", display: "flex", alignItems: "flex-end", gap: 10, minHeight: 72 }}>
        <h1 className="display" style={{ fontSize: "clamp(46px, 14vw, 66px)" }}>
          TODAY
        </h1>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 18, paddingBottom: 2 }}>
          {WEEKDAY_JA[now.getDay()]}
        </span>
        {plan && <WeatherDisc plan={plan} />}
      </header>

      <Ticker plan={plan} now={now} />

      <button
        type="button"
        onClick={() => ctx.go("notes")}
        style={{ display: "flex", alignItems: "center", gap: 12, border: 0, background: "transparent", padding: 0, textAlign: "left" }}
        aria-label={`Oni is ${MOOD_LABEL[mood].en}.${ctx.oni?.has_history ? ` Closet alive ${ctx.oni.closet_alive_pct}%.` : ""} Open notes.`}
      >
        <Oni mood={mood} size={52} />
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>
              {MOOD_LABEL[mood].en} <span lang="ja" style={{ fontWeight: 500, fontSize: 12 }}>{MOOD_LABEL[mood].ja}</span>
            </span>
            <span className="label">{ctx.oni?.has_history ? `CLOSET ALIVE ${ctx.oni.closet_alive_pct}%` : "NO WEAR HISTORY YET"}</span>
          </span>
          {ctx.oni?.has_history && <AliveBar pct={ctx.oni.closet_alive_pct} />}
        </span>
      </button>

      <Yesterday ctx={ctx} />
      {load.state === "ready" && look && wornLook !== lookIndex && <RescueLine look={look} />}

      {load.state === "empty" && <EmptyCloset msg={load.msg} ctx={ctx} />}
      {load.state === "error" && (
        <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
          <strong>The oni couldn't plan today.</strong>
          <span className="small">{load.msg}</span>
          <button type="button" className="btn press" onClick={() => replan("")}>
            Try again →
          </button>
        </div>
      )}

      {(load.state === "ready" || load.state === "thinking" || load.state === "loading") && (
        <section aria-label="Today's outfit" style={{ position: "relative", marginTop: 14 }}>
          <div
            aria-hidden="true"
            style={{ position: "absolute", inset: "6px -2px -6px 10px", border: "var(--line)", borderRadius: 12, background: "var(--paper)", transform: "rotate(3deg)" }}
          >
            {plan && plan.looks.length > 1 && (
              <span
                className="label"
                style={{ position: "absolute", top: -1, right: 18, fontSize: 9, padding: "2px 6px", background: "var(--sumi)", color: "var(--washi)", borderRadius: "0 0 4px 4px" }}
              >
                NEXT · LOOK {LOOK_LETTERS[(lookIndex + 1) % plan.looks.length]}
              </span>
            )}
          </div>
          <div
            aria-hidden="true"
            style={{ position: "absolute", inset: "4px 8px -4px -2px", border: "var(--line)", borderRadius: 12, background: "var(--washi-2)", transform: "rotate(-2deg)" }}
          />

          <div className="card" style={{ position: "relative", padding: 10, display: "flex", flexDirection: "column", gap: 10 }}>
            {lookIndex === 0 && load.state === "ready" && (
              <span
                lang="ja"
                role="img"
                aria-label="Picked by the monster"
                className="hanko"
                style={{ position: "absolute", zIndex: 3, top: -18, right: 10, animation: "stamp .5s cubic-bezier(.2,.9,.3,1.2) .4s both" }}
              >
                選
              </span>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingRight: 62 }}>
              <span className="label" style={{ fontSize: 11 }}>
                {lookIndex === 0 ? "TODAY'S PICK" : "ALSO GOOD"} · LOOK {LOOK_LETTERS[lookIndex]}
              </span>
              {plan && <span className="label" style={{ fontWeight: 400, fontSize: 11 }}>{lookIndex + 1} / {plan.looks.length}</span>}
            </div>

            {load.state !== "ready" || !look ? (
              <Thinking slow={load.state === "thinking" && ctx.health?.mode === "live"} full={full} />
            ) : (
              <>
                <Collage key={plan!.id + lookIndex} items={look.items} onOpen={ctx.openItem} onTryOn={() => ctx.openTryOn(plan!, lookIndex)} />
                <h2 className="display" style={{ fontSize: 22, lineHeight: 1.05 }}>{look.name}</h2>
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55 }}>{look.why}</p>
              </>
            )}

            <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
              {wornLook === lookIndex ? (
                <button type="button" className="btn primary press" style={{ flex: 1.2 }} onClick={() => ctx.openCheckin(plan, lookIndex)}>
                  Worn ✓ · Check in →
                </button>
              ) : (
                <button type="button" className="btn primary press" style={{ flex: 1.2 }} disabled={load.state !== "ready" || wearing} onClick={wear}>
                  {wearing ? "Logging…" : "Wear this →"}
                </button>
              )}
              <button
                type="button"
                className="btn press"
                style={{ flex: 1 }}
                disabled={!plan || plan.looks.length < 2 || load.state !== "ready"}
                onClick={() => plan && setLookIndex((lookIndex + 1) % plan.looks.length)}
              >
                Next look ⇄
              </button>
            </div>

            {!full && load.state === "ready" && look && (
              <button
                type="button"
                className="press"
                aria-expanded={more}
                onClick={() => setMore(!more)}
                style={{ border: 0, background: "transparent", padding: "2px 0", display: "flex", justifyContent: "space-between", fontWeight: 700, fontSize: 13 }}
              >
                <span>{more ? "Less" : "More: finishing touches, colours, tweaks"}</span>
                <span aria-hidden="true">{more ? "▴" : "▾"}</span>
              </button>
            )}
            {open && load.state === "ready" && look && <Touches plan={plan!} lookIndex={lookIndex} ctx={ctx} />}

            {open && <div role="group" aria-label="Adjust the pick" style={{ display: "flex", gap: 6, flexWrap: "wrap", paddingBottom: 2 }}>
              {ADJUST.map((a) => (
                <button
                  key={a.label}
                  type="button"
                  className="chip press"
                  aria-pressed={!!adjust[a.label]}
                  disabled={load.state !== "ready"}
                  onClick={() => toggle(a.label)}
                >
                  {a.label}
                  {adjust[a.label] ? " ✓" : ""}
                </button>
              ))}
              <button
                type="button"
                className="chip shu press"
                disabled={load.state !== "ready"}
                onClick={() => replan(plan?.notes ?? "", true)}
                aria-label="Ask the oni for a fresh pick"
              >
                Re-roll ↻
              </button>
            </div>}
          </div>
        </section>
      )}

      {plan && load.state === "ready" && open && <PlanSource plan={plan} onOpen={() => setShowTrace(true)} />}
      {showTrace && plan && <TraceSheet plan={plan} onClose={() => setShowTrace(false)} />}

      <button
        type="button"
        className="press night"
        onClick={() => ctx.openCheckin(plan, wornLook)}
        style={{
          marginTop: 8,
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 12px",
          border: "var(--line)",
          borderRadius: 12,
          background: "var(--sumi)",
          color: "var(--washi)",
          boxShadow: "3px 3px 0 var(--ai)",
          textAlign: "left",
        }}
      >
        <span style={{ paddingRight: 14, paddingTop: 6 }}>
          <Oni mood="sleepy" size={34} night />
        </span>
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>Evening check-in</span>
          <span className="small" style={{ color: "var(--mist)" }}>Tell the oni how it went. It learns for tomorrow.</span>
        </span>
        <span aria-hidden="true" style={{ fontWeight: 700 }}>→</span>
      </button>
    </main>
  );
}

// ------------------------------------------------------------------ pieces

// The morning question: one tap instead of logging every wear. Asked once about yesterday's pick,
// only when it was shown and nothing was logged. "Yes" counts the wear (and any rescue).
function Yesterday({ ctx }: { ctx: AppCtx }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.yesterday().then((r) => setPlan(r.plan)).catch(() => {});
  }, []);
  if (!plan || !plan.looks.length) return null;

  const hero = plan.looks[0];
  const star = hero.items.find((i) => i.id === hero.rediscovered_id) ?? hero.items[0];
  const answer = async (look: number | null) => {
    setBusy(true);
    try {
      const { worn } = await api.answerYesterday(look);
      setPlan(null);
      const rescued = worn?.rescued ?? [];
      ctx.toast(
        !worn ? "No worries. I'll keep it in mind for another day."
          : rescued.length > 1 ? `Rescued ${rescued.length} forgotten pieces at once. The oni is fed.`
          : rescued.length ? `Rescued! Your ${rescued[0].name} got out after ${rescued[0].days} days.`
          : "Logged. Thanks for wearing what you own.",
      );
      if (worn) ctx.bumpWardrobe();
    } catch (e) {
      ctx.toast((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <section aria-label="Yesterday's outfit" className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10, animation: "rise .3s ease-out both" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ display: "flex", flex: "none" }}>
          {hero.items.slice(0, 3).map((it, i) => (
            <span key={it.id} className="halftone" style={{ width: 40, height: 40, borderRadius: 8, border: "var(--line)", padding: 2, marginLeft: i ? -10 : 0, background: "var(--paper)" }}>
              <img className="cutout" src={it.cutout_url} alt="" />
            </span>
          ))}
        </span>
        <strong style={{ fontSize: 15, lineHeight: 1.35 }}>
          Did the {star ? itemName(star).toLowerCase() : "outfit"} make it out yesterday?
        </strong>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button type="button" className="btn primary press" style={{ height: 38, fontSize: 13, flex: 1 }} disabled={busy} onClick={() => answer(0)}>
          Yes, I wore it
        </button>
        <button type="button" className="btn press" style={{ height: 38, fontSize: 13, flex: 1 }} disabled={busy} onClick={() => answer(null)}>
          No
        </button>
      </div>
      {plan.looks.length > 1 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span className="small muted">Wore another pick?</span>
          {plan.looks.slice(1).map((lk, n) => (
            <button key={n} type="button" className="chip press" style={{ height: 28, fontSize: 12, padding: "0 10px" }} disabled={busy} onClick={() => answer(n + 1)}>
              Look {LOOK_LETTERS[n + 1]}: {lk.items.slice(0, 2).map(shortName).join(" + ")}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

// Garments English treats as plural ("the jeans have"), for the oni's sentences.
const PLURAL = /(pants|jeans|trousers|shorts|chinos|leggings|joggers|sweatpants|overalls|sneakers|trainers|boots|shoes|socks)$/i;

// The oni's voice over the look: how long its most forgotten piece has waited. Estimates say "about".
function RescueLine({ look }: { look: Look }) {
  const ranked = look.items.map((i) => ({ i, d: idleDays(i) })).sort((a, b) => b.d - a.d);
  const top = ranked[0];
  if (!top || top.d < 30) return null;
  const days = `${top.i.worn_estimated ? "about " : ""}${top.d} days`;
  return (
    <p
      aria-live="polite"
      style={{
        margin: "2px 0 -6px", alignSelf: "flex-start", border: "var(--line)", borderRadius: "2px 12px 12px 12px", padding: "8px 12px",
        background: "var(--washi)", fontSize: 14, lineHeight: 1.45, fontWeight: 500, animation: "rise .3s ease-out both",
      }}
    >
      Your <strong>{itemName(top.i).toLowerCase()}</strong> {PLURAL.test(top.i.tags?.subtype ?? "") ? "have" : "has"} been in here {days}. Today{" "}
      {PLURAL.test(top.i.tags?.subtype ?? "") ? "they get" : "it gets"} out.
    </p>
  );
}

function partNow(plan: Plan): [string, WeatherPart] | null {
  const parts = plan.weather.parts;
  if (!parts) return null;
  const h = new Date().getHours();
  const key = h < 12 ? "morning" : h < 18 ? "afternoon" : "evening";
  return [key, parts[key]];
}

function WeatherDisc({ plan }: { plan: Plan }) {
  const p = partNow(plan);
  if (!p) return null;
  const [, part] = p;
  const parts = plan.weather.parts!;
  const rainy = (Object.entries(parts) as [string, WeatherPart][]).find(([, w]) => w.rain_chance_pct >= 40);
  const sub = rainy ? `RAIN ${rainy[0].slice(0, 3).toUpperCase()}` : `FEELS ${Math.round(part.feels_like_low_c)}°`;
  return (
    <span
      role="img"
      aria-label={`${part.temp_c[1]} degrees, ${part.sky}. ${sub.toLowerCase()}`}
      style={{
        position: "absolute",
        right: 0,
        top: -14,
        width: 66,
        height: 66,
        borderRadius: "50%",
        background: "var(--ai)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        transform: "rotate(8deg)",
        fontFamily: "var(--mono)",
        fontSize: 9,
        fontWeight: 700,
        lineHeight: 1.25,
        textAlign: "center",
      }}
    >
      <span className="display" style={{ fontSize: 20 }}>{part.temp_c[1]}°</span>
      <span>{sub}</span>
    </span>
  );
}

function Ticker({ plan, now }: { plan: Plan | null; now: Date }) {
  const date = now.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }).toUpperCase();
  const bits = [date, "今日のコーデ"];
  if (plan) {
    plan.calendar.events.forEach((e) => bits.push(`${e.start} ${e.title.toUpperCase()}`));
    if (!plan.calendar.events.length) bits.push("NO PLANS TODAY");
    bits.push(plan.weather_summary.toUpperCase());
  }
  const text = bits.join(" ★ ") + " ★ ";
  return (
    <div
      aria-label={"Today at a glance: " + bits.join(", ")}
      style={{
        margin: "0 -16px",
        height: 30,
        background: "var(--sumi)",
        color: "var(--washi)",
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
      }}
    >
      <div aria-hidden="true" className="label" style={{ display: "flex", whiteSpace: "nowrap", fontSize: 11, animation: "ticker 26s linear infinite" }}>
        <span style={{ paddingRight: 24 }}>{text}</span>
        <span style={{ paddingRight: 24 }}>{text}</span>
      </div>
    </div>
  );
}

export function AliveBar({ pct, from }: { pct: number; from?: number }) {
  return (
    <div
      role="img"
      aria-label={`Closet alive ${pct}%`}
      style={{ height: 10, borderRadius: 5, border: "var(--line)", overflow: "hidden", position: "relative", background: "var(--washi)" }}
    >
      <div
        style={
          {
            height: "100%",
            width: `${pct}%`,
            background: pct < 25 ? "var(--shu)" : "var(--sumi)",
            "--from": `${from ?? pct}%`,
            "--to": `${pct}%`,
            animation: from !== undefined ? "fill 1s ease-out .6s both" : undefined,
          } as React.CSSProperties
        }
      />
      {[25, 60].map((m) => (
        <span key={m} aria-hidden="true" style={{ position: "absolute", left: `${m}%`, top: 0, bottom: 0, borderLeft: "1px dashed var(--ghost)" }} />
      ))}
    </div>
  );
}

// Cutouts laid out like a collage on the riso halftone: slight tilts, overlapping, staggered rise.
const FRAMES: Record<number, { l: number; t: number; w: number; h: number; r: number }[]> = {
  1: [{ l: 22, t: 4, w: 56, h: 88, r: -3 }],
  2: [
    { l: 2, t: 4, w: 52, h: 86, r: -5 },
    { l: 46, t: 8, w: 52, h: 86, r: 4 },
  ],
  3: [
    { l: 0, t: 4, w: 42, h: 70, r: -6 },
    { l: 30, t: 16, w: 40, h: 76, r: 3 },
    { l: 60, t: 2, w: 40, h: 82, r: -3 },
  ],
  4: [
    { l: 0, t: 2, w: 38, h: 62, r: -6 },
    { l: 30, t: 10, w: 34, h: 54, r: 4 },
    { l: 62, t: 2, w: 36, h: 70, r: -3 },
    { l: 26, t: 58, w: 46, h: 38, r: 6 },
  ],
};

// The unworn sticker goes by the item's own idle days, not the plan's rediscovered_id: the rule
// picker treats never-worn items as forgotten, which would flag clothes scanned this morning.
function Collage({ items, onOpen, onTryOn }: { items: Item[]; onOpen: (i: Item) => void; onTryOn: () => void }) {
  const frames = FRAMES[Math.min(items.length, 4)] ?? FRAMES[4];
  return (
    <div className="halftone" style={{ position: "relative", height: 236, borderRadius: 8, overflow: "hidden", border: "var(--line)" }}>
      <button
        type="button"
        className="chip press"
        onClick={onTryOn}
        style={{ position: "absolute", zIndex: 10, right: 8, bottom: 8, height: 32, fontSize: 12, padding: "0 10px" }}
      >
        Try it on <span lang="ja">試着</span> →
      </button>
      {items.slice(0, 4).map((it, i) => {
        const f = frames[i];
        const idle = idleDays(it);
        const badge = idle >= 30 ? `${idle}日 UNWORN` : null;
        return (
          <button
            key={it.id}
            type="button"
            onClick={() => onOpen(it)}
            aria-label={`${shortName(it)}, open details`}
            style={
              {
                "--r": `${f.r}deg`,
                position: "absolute",
                left: `${f.l}%`,
                top: `${f.t}%`,
                width: `${f.w}%`,
                height: `${f.h}%`,
                zIndex: i + 1,
                padding: 0,
                border: 0,
                background: "transparent",
                transform: `rotate(${f.r}deg)`,
                animation: `rise-tilt .45s ease-out ${0.08 * i}s both`,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              } as React.CSSProperties
            }
          >
            <img className="cutout" src={it.cutout_url} alt="" style={{ flex: 1, minHeight: 0 }} />
            <span
              style={{
                marginTop: -6,
                background: "var(--washi)",
                border: "var(--line)",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 11,
                fontWeight: 700,
                whiteSpace: "nowrap",
                boxShadow: "2px 2px 0 var(--sumi)",
              }}
            >
              {"①②③④"[i]} {shortName(it)}
            </span>
            {badge && (
              <span className="sticker" style={{ position: "absolute", top: 6, left: -2, animation: "wobble 3s ease-in-out infinite" }}>
                {badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function Thinking({ slow, full }: { slow: boolean; full: boolean }) {
  return (
    <div
      className="halftone"
      style={{ height: 236, borderRadius: 8, border: "var(--line)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}
    >
      <Oni mood="calm" size={64} />
      <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "4px 10px", fontWeight: 700, fontSize: 13 }}>
        <span className="spinner-dots">Checking the weather and your day</span>
      </span>
      {slow && (
        <span className="label" style={{ background: "var(--washi)", padding: "2px 6px" }}>
          {full ? "MUSE SPARK OPEN · ~15S" : "ABOUT 15 SECONDS"}
        </span>
      )}
    </div>
  );
}

// Who made the plan, and the way into its step-by-step trace.
function PlanSource({ plan, onOpen }: { plan: Plan; onOpen: () => void }) {
  const t = plan.trace;
  const who =
    plan.source === "rules" ? "RULE PICKER" : (t.model ?? t.provider ?? "MODEL").replace("meta-models/", "").toUpperCase();
  const extra = t.prebuilt ? "READY AHEAD" : t.cached || plan.source === "cache" ? "CACHED" : t.seconds ? `${t.seconds}S` : "";
  const steps = t.steps?.length ?? 0;
  return (
    <button
      type="button"
      className="press"
      onClick={onOpen}
      style={{
        marginTop: 6, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "8px 12px",
        border: "1.5px dashed var(--sumi)", borderRadius: 8, background: "transparent", textAlign: "left",
      }}
    >
      <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <strong style={{ fontSize: 13 }}>How the oni decided</strong>
        <span className="label muted" style={{ fontWeight: 400, fontSize: 9 }}>
          {who}
          {extra ? ` · ${extra}` : ""}
          {steps ? ` · ${steps} STEPS` : ""}
          {t.repairs ? ` · ${t.repairs} REPAIR` : ""}
          {plan.notes ? ` · “${plan.notes.toUpperCase()}”` : ""}
        </span>
      </span>
      <span aria-hidden="true" style={{ fontWeight: 700 }}>→</span>
    </button>
  );
}

function EmptyCloset({ msg, ctx }: { msg: string; ctx: AppCtx }) {
  const [busy, setBusy] = useState(false);
  const empty = msg.startsWith("Your closet is empty");
  const sample = async () => {
    setBusy(true);
    try {
      await api.loadSample();
      ctx.bumpWardrobe(); // Today reloads and plans from the sample closet
    } catch (e) {
      ctx.toast((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="card" style={{ marginTop: 10, padding: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
      <Oni mood="restless" size={80} />
      <h2 className="display" style={{ fontSize: 26 }}>FEED ME CLOTHES</h2>
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>
        {empty ? "Your closet is empty. Lay 4–8 things flat, take a photo, and I'll pick an outfit from what you own." : msg}
      </p>
      <button type="button" className="btn shu press block" onClick={() => ctx.go("scan")}>
        Scan my clothes →
      </button>
      {empty && (
        <button type="button" className="btn press block" disabled={busy} onClick={sample}>
          {busy ? "Loading…" : "Try a sample closet"}
        </button>
      )}
    </div>
  );
}
