import { useEffect, useState } from "react";
import { api, type CalendarEvent, type Plan, type UpcomingEvent } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";
import { useSwipe } from "../swipe";
import { Collage, LookDots } from "./Today";

// Dress for an occasion: the week's events (the ones on Today's ticker), each read as an occasion
// (how dressed up, evening, outdoors), and looks planned for just that event. Something not on the
// calendar ("job interview Friday") can be typed in. Plans for one event never replace the day's pick.

const LETTERS = ["A", "B", "C"];
const WEEKDAY = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d;
};

export function dayLabel(day: string): string {
  if (day === iso(new Date())) return "TODAY";
  if (day === iso(addDays(1))) return "TMRW";
  const d = new Date(day + "T12:00:00");
  return `${WEEKDAY[d.getDay()]} ${d.getDate()}`;
}

const savedFor = (day: string) => {
  const l = dayLabel(day);
  return l === "TMRW" ? "tomorrow" : l.charAt(0) + l.slice(1).toLowerCase();
};

type Open = { event: CalendarEvent; day: string; planId: string | null } | { typing: true };

export function ComingUp({ ctx }: { ctx: AppCtx }) {
  const [data, setData] = useState<{ calendar: string; events: UpcomingEvent[] } | null>(null);
  const [open, setOpen] = useState<Open | null>(null);
  const [all, setAll] = useState(false);

  const load = () => {
    api.occasions().then(setData).catch(() => setData({ calendar: "none", events: [] }));
  };
  useEffect(load, [ctx.wardrobeVersion, ctx.refreshKey]);

  const events = data?.events ?? [];
  const shown = all ? events : events.slice(0, 4);
  return (
    <section id="occasions" aria-label="Dress for an occasion" className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10, marginTop: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span className="label">
          DRESS FOR AN OCCASION · <span lang="ja">行事</span>
        </span>
        {data && data.calendar !== "none" && <span className="label" style={{ fontWeight: 400 }}>NEXT 7 DAYS</span>}
      </div>

      {data && !events.length && (
        <span className="small">
          {data.calendar === "none" ? "Connect your calendar and the oni dresses you for each plan on it." : "Nothing on your calendar this week."}
        </span>
      )}

      {shown.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {shown.map((e, n) => (
            <li key={`${e.day}-${e.start}-${e.title}-${n}`}>
              <button
                type="button"
                className="press"
                onClick={() => setOpen({ event: { title: e.title, start: e.start, end: e.end, location: e.location, dress_code: e.dress_code }, day: e.day, planId: e.plan_id })}
                style={{
                  width: "100%", display: "grid", gridTemplateColumns: "54px 1fr auto", alignItems: "center", gap: 10, padding: "8px 10px",
                  border: "var(--line)", borderRadius: 10, background: "var(--washi)", textAlign: "left",
                }}
              >
                <span className="label" style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                  <span>{dayLabel(e.day)}</span>
                  <span style={{ fontWeight: 400 }}>{e.start === "all day" ? "ALL DAY" : e.start}</span>
                </span>
                <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <strong style={{ fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.title}</strong>
                  <span className="small" style={{ fontSize: 12 }}>{e.read.label}</span>
                </span>
                <span className="label" style={{ fontSize: 11, color: e.plan_id ? undefined : "var(--shu)" }}>
                  {e.plan_id ? "PLANNED ✓" : "PLAN →"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="chip press" onClick={() => setOpen({ typing: true })}>
          + Something else coming up
        </button>
        {events.length > 4 && (
          <button type="button" className="chip press" onClick={() => setAll(!all)}>
            {all ? "Fewer" : `All ${events.length}`}
          </button>
        )}
        {data?.calendar === "none" && (
          <button type="button" className="chip press" onClick={ctx.openSetup}>
            Connect calendar →
          </button>
        )}
      </div>

      {open && (
        <OccasionSheet
          ctx={ctx}
          start={open}
          onClose={() => {
            setOpen(null);
            load();
          }}
        />
      )}
    </section>
  );
}

function OccasionSheet({ ctx, start, onClose }: { ctx: AppCtx; start: Open; onClose: () => void }) {
  const [target, setTarget] = useState<{ event: CalendarEvent; day: string } | null>("typing" in start ? null : { event: start.event, day: start.day });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [typed, setTyped] = useState<{ event: CalendarEvent; day: string } | null>(null); // a typed occasion, to edit again
  const [error, setError] = useState<string | null>(null);
  const [look, setLook] = useState(0);
  const [busy, setBusy] = useState(false);

  const plan_ = async (t: { event: CalendarEvent; day: string }, fresh = false, id: string | null = null) => {
    setTarget(t);
    setPlan(null);
    setError(null);
    setLook(0);
    try {
      setPlan(id ? await api.plan(id) : await api.planOccasion(t.event, t.day, fresh));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    if (!("typing" in start)) plan_({ event: start.event, day: start.day }, false, start.planId);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && !e.defaultPrevented && onClose(); // a sheet on top closes first
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const today = !!target && target.day === iso(new Date());
  const looks = plan?.looks.length ?? 0;
  const step = (d: number) => looks > 1 && setLook((look + d + looks) % looks);
  const swipe = useSwipe(() => step(1), () => step(-1));
  const read = plan?.occasion?.read;
  const current = plan?.looks[look];
  const stretch = plan?.trace.stretch?.look === look;

  const wear = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      const result = await api.wear(plan.id, look);
      onClose();
      ctx.showWorn(result, plan, look);
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Dress for an occasion" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" style={{ gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            OCCASION · <span lang="ja">行事</span>
          </span>
        </div>

        {!target ? (
          <TypeOccasion initial={typed} onPlan={(t) => {
            setTyped(t);
            plan_(t);
          }} />
        ) : (
          <>
            {typed && (
              <button type="button" className="chip press" style={{ alignSelf: "flex-start", height: 30, fontSize: 12 }} onClick={() => {
                setTarget(null);
                setPlan(null);
                setError(null);
              }}>
                ‹ Change details
              </button>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="label">
                {dayLabel(target.day)}
                {target.event.start && target.event.start !== "all day" ? ` · ${target.event.start}` : ""}
                {target.event.location ? ` · ${target.event.location.toUpperCase()}` : ""}
              </span>
              <h1 className="display" style={{ fontSize: 30, lineHeight: 1.05 }}>{target.event.title}</h1>
            </div>

            {read && (
              <div className="card" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6, background: "var(--paper)" }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {read.label.split(" · ").map((b) => (
                    <span key={b} className="label" style={{ border: "var(--line)", borderRadius: 4, padding: "2px 6px", fontSize: 10, background: "var(--washi)" }}>
                      {b.toUpperCase()}
                    </span>
                  ))}
                </div>
                <span style={{ fontSize: 14, lineHeight: 1.5 }}>{read.advice}</span>
                <span className="small muted" style={{ fontSize: 11 }}>Read from {read.why}.</span>
              </div>
            )}

            {error ? (
              <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                <strong>The oni couldn't plan this one.</strong>
                <span className="small">{error}</span>
                <button type="button" className="btn press" onClick={() => plan_(target)}>Try again →</button>
              </div>
            ) : !plan || !current ? (
              <div className="halftone" style={{ height: 236, borderRadius: 8, border: "var(--line)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
                <Oni mood="calm" size={60} />
                <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "4px 10px", fontWeight: 700, fontSize: 13 }}>
                  <span className="spinner-dots">Reading the occasion</span>
                </span>
              </div>
            ) : (
              <>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span className="label" style={{ fontSize: 11, color: stretch ? "var(--shu)" : undefined }}>
                    {stretch ? "STRETCH" : look === 0 ? "THE PICK" : "ALSO GOOD"} · LOOK {LETTERS[look]}
                  </span>
                  {looks > 1 && <LookDots n={looks} at={look} onPick={setLook} />}
                </div>
                <div {...swipe}>
                  <Collage key={plan.id + look} items={current.items} onOpen={ctx.openItem} onTryOn={() => ctx.openTryOn(plan, look)} />
                </div>
                <h2 className="display" style={{ fontSize: 22, lineHeight: 1.05 }}>{current.name}</h2>
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55 }}>{current.why}</p>
                <div style={{ display: "flex", gap: 8 }}>
                  <button type="button" className="btn press" aria-label="Previous look" style={{ flex: "none", width: 52, padding: 0 }} disabled={looks < 2} onClick={() => step(-1)}>
                    ‹
                  </button>
                  {today ? (
                    <button type="button" className="btn primary press" style={{ flex: 1.2 }} disabled={busy} onClick={wear}>
                      {busy ? "Logging…" : "Wear this →"}
                    </button>
                  ) : (
                    <span className="btn" style={{ flex: 1.2, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.85 }}>
                      Saved for {savedFor(target.day)} ✓
                    </span>
                  )}
                  <button type="button" className="btn press" aria-label="Next look" style={{ flex: "none", width: 52, padding: 0 }} disabled={looks < 2} onClick={() => step(1)}>
                    ›
                  </button>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="label" style={{ fontWeight: 400, fontSize: 10 }}>{looks > 1 ? "SWIPE FOR MORE LOOKS ⇆" : ""}</span>
                  <button type="button" className="chip press" style={{ height: 28, fontSize: 12 }} onClick={() => plan_(target, true)}>
                    ↻ New picks
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const IDEAS = ["Job interview", "First date", "Wedding", "Dinner out", "Gym", "Presentation", "Party", "Brunch"];
// Times as parts of the day: the forecast is read by part, and a native time picker shows as an empty box on many phones.
const TIMES: [string, string][] = [["Morning", "09:00"], ["Afternoon", "14:00"], ["Evening", "19:00"], ["All day", "all day"]];

function TypeOccasion({ initial, onPlan }: { initial: { event: CalendarEvent; day: string } | null; onPlan: (t: { event: CalendarEvent; day: string }) => void }) {
  const days = Array.from({ length: 10 }, (_, n) => iso(addDays(n))); // two wide + two full rows of four
  const [title, setTitle] = useState(initial?.event.title ?? "");
  const [day, setDay] = useState(initial && days.includes(initial.day) ? initial.day : days[0]);
  const [time, setTime] = useState(initial?.event.start ?? "19:00");
  const [place, setPlace] = useState(initial?.event.location ?? "");
  const field = { display: "flex", alignItems: "center", height: 46, padding: "0 14px", border: "var(--line)", borderRadius: 23, background: "var(--washi)" } as const;
  const input = { flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent", fontSize: 15, color: "inherit" } as const;
  const chip = { height: 32, fontSize: 12, padding: "0 10px" } as const;
  const label = (d: string, n: number) => (n === 0 ? "Today" : n === 1 ? "Tomorrow" : dayLabel(d).charAt(0) + dayLabel(d).slice(1).toLowerCase());

  return (
    <form
      style={{ display: "flex", flexDirection: "column", gap: 14 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (!title.trim()) return;
        onPlan({ day, event: { title: title.trim(), start: time, location: place.trim() || undefined } });
      }}
    >
      <h1 className="display" style={{ fontSize: 30, lineHeight: 1.05 }}>WHAT'S COMING UP?</h1>

      <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span className="label">WHAT IS IT</span>
        <label style={field}>
          <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>What is it</span>
          <input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder="Type it, or pick one below" style={input} />
        </label>
        <div role="radiogroup" aria-label="Ideas" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {IDEAS.map((i) => (
            <button key={i} type="button" role="radio" aria-checked={title === i} className="chip press" style={chip} onClick={() => setTitle(i)}>
              {i}
            </button>
          ))}
        </div>
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span className="label">WHEN</span>
        <div role="radiogroup" aria-label="Day" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 6 }}>
          {days.map((d, n) => (
            <button key={d} type="button" role="radio" aria-checked={day === d} className="chip press" style={{ ...chip, padding: 0, gridColumn: n < 2 ? "span 2" : undefined }} onClick={() => setDay(d)}>
              {label(d, n)}
            </button>
          ))}
        </div>
        <div role="radiogroup" aria-label="Time of day" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 6 }}>
          {TIMES.map(([name, t]) => (
            <button key={t} type="button" role="radio" aria-checked={time === t} className="chip press" style={{ ...chip, padding: 0 }} onClick={() => setTime(t)}>
              {name}
            </button>
          ))}
        </div>
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span className="label">WHERE <span style={{ fontWeight: 400 }}>(OPTIONAL)</span></span>
        <label style={field}>
          <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Where</span>
          <input value={place} maxLength={120} onChange={(e) => setPlace(e.target.value)} placeholder="e.g. rooftop bar, office, park" style={input} />
        </label>
        <div role="group" aria-label="Indoors or outside" style={{ display: "flex", gap: 6 }}>
          {["Indoors", "Outside"].map((w) => (
            <button key={w} type="button" aria-pressed={place === w} className="chip press" style={chip} onClick={() => setPlace(place === w ? "" : w)}>
              {w}
            </button>
          ))}
        </div>
      </section>

      <span className="small muted">The time picks the right hours of the forecast; "Outside" tells the oni to dress you for the weather.</span>
      <button type="submit" className="btn primary press block" style={{ height: 50 }} disabled={!title.trim()}>
        {title.trim() ? `Plan for ${title.trim().length > 22 ? "it" : title.trim().toLowerCase()} →` : "Say what it is first"}
      </button>
    </form>
  );
}
