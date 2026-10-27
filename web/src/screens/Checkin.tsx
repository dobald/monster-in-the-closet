import { useState } from "react";
import { api, shortName, type CheckinAnswers, type CheckinResult, type Plan } from "../api";
import type { AppCtx } from "../App";
import Oni from "../Oni";

// Evening check-in (wireframe 4b): three quick answers, an optional note, then the oni's reply
// and whatever it learned for tomorrow.

const TEMPS: { id: CheckinAnswers["temperature"]; label: string }[] = [
  { id: "cold", label: "Cold" },
  { id: "just_right", label: "Just right" },
  { id: "warm", label: "Warm" },
];
const FEELS: { id: CheckinAnswers["feeling"]; label: string }[] = [
  { id: "meh", label: "Meh" },
  { id: "fine", label: "Fine" },
  { id: "good", label: "Good" },
  { id: "iconic", label: "Iconic" },
];
const TAGS = ["Compliments", "Comfy", "Too formal", "Rained on", "Itchy"];

export default function Checkin({ plan, lookIndex, ctx, onDone }: { plan: Plan | null; lookIndex: number | null; ctx: AppCtx; onDone: () => void }) {
  const [temp, setTemp] = useState<CheckinAnswers["temperature"] | null>(null);
  const [feel, setFeel] = useState<CheckinAnswers["feeling"] | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<CheckinResult | null>(null);

  const look = plan && lookIndex !== null ? plan.looks[lookIndex] : null;
  const time = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  const send = async () => {
    if (!temp || !feel) return;
    setSending(true);
    try {
      setResult(await api.checkin({ plan_id: plan?.id, temperature: temp, feeling: feel, tags, note: note.trim() }));
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Evening check-in">
      <div className="sheet night">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onDone}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            {time} · EVENING CHECK-IN · <span lang="ja">夜</span>
          </span>
        </div>

        <header style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <h1 className="display" style={{ fontSize: 40, lineHeight: 1 }}>
              HOW DID
              <br />
              IT GO?
            </h1>
            <span lang="ja" style={{ fontSize: 13, fontWeight: 500, color: "var(--mist)" }}>
              今日はどうだった？
            </span>
          </div>
          <span style={{ position: "relative" }}>
            <span aria-hidden="true" style={{ position: "absolute", right: -6, top: -10, width: 54, height: 54, borderRadius: "50%", background: "var(--ai)" }} />
            <span aria-hidden="true" style={{ position: "absolute", right: 2, top: -16, width: 46, height: 46, borderRadius: "50%", background: "var(--sumi)" }} />
            <Oni mood={result ? "sleepy" : "calm"} size={84} night />
          </span>
        </header>

        {look && (
          <div aria-label="Today's look" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {look.items.map((it) => (
              <span
                key={it.id}
                title={shortName(it)}
                style={{ width: 48, height: 48, border: "1.5px solid var(--washi)", borderRadius: 6, background: "var(--sumi-2)", padding: 3 }}
              >
                <img src={it.cutout_url} alt={shortName(it)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
              </span>
            ))}
            <span className="label" style={{ fontWeight: 400, marginLeft: 4, lineHeight: 1.4 }}>
              {look.name.toUpperCase()}
            </span>
          </div>
        )}

        {!result ? (
          <>
            <Question n="01" title="TEMPERATURE">
              <div role="radiogroup" aria-label="Temperature" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, paddingRight: 2 }}>
                {TEMPS.map((t) => (
                  <button key={t.id} type="button" role="radio" aria-checked={temp === t.id} className="chip press" style={{ height: 46, borderRadius: 8, fontSize: 14 }} onClick={() => setTemp(t.id)}>
                    {t.label}
                  </button>
                ))}
              </div>
            </Question>

            <Question n="02" title="HOW DID YOU FEEL IN IT?">
              <div role="radiogroup" aria-label="Feeling" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8, paddingRight: 2 }}>
                {FEELS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    role="radio"
                    aria-checked={feel === f.id}
                    className={"chip press" + (f.id === "iconic" ? " iconic" : "")}
                    style={{ height: 46, borderRadius: 8, padding: 0 }}
                    onClick={() => setFeel(f.id)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </Question>

            <Question n="03" title="ANYTHING ELSE? (PICK ANY)">
              <div role="group" aria-label="Tags" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {TAGS.map((t) => {
                  const on = tags.includes(t);
                  return (
                    <button key={t} type="button" aria-pressed={on} className="chip press" onClick={() => setTags(on ? tags.filter((x) => x !== t) : [...tags, t])}>
                      {t}
                      {on ? " ✓" : ""}
                    </button>
                  );
                })}
              </div>
              <label style={{ position: "relative", display: "block", marginTop: 4 }}>
                <span className="label" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
                  Note for the oni
                </span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  maxLength={400}
                  placeholder="Tell the oni anything, e.g. the studio was boiling"
                  style={{
                    width: "100%",
                    resize: "none",
                    border: "1.5px solid var(--washi)",
                    borderRadius: 8,
                    background: "var(--sumi-2)",
                    color: "var(--washi)",
                    padding: "10px 12px",
                    fontSize: 14,
                    outline: "none",
                  }}
                />
              </label>
            </Question>

            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="btn press block"
              disabled={!temp || !feel || sending}
              onClick={send}
              style={{ background: "var(--washi)", color: "var(--sumi)", borderColor: "var(--washi)", boxShadow: "3px 3px 0 var(--shu)", height: 52 }}
            >
              {sending ? <span className="spinner-dots">The oni is thinking</span> : !temp || !feel ? "Pick a temperature and a feeling" : "Tell the oni →"}
            </button>
          </>
        ) : (
          <>
            <div
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
                border: "1.5px solid var(--washi)",
                borderRadius: "12px 12px 12px 2px",
                padding: "10px 12px",
                background: "var(--sumi-2)",
                animation: "rise .35s ease-out both",
              }}
            >
              <span style={{ flex: "none", color: "var(--blush)", fontWeight: 700, fontSize: 14 }}>Oni:</span>
              <p style={{ margin: 0, fontSize: 15, lineHeight: 1.5 }}>{result.oni_reply}</p>
            </div>

            {result.learned?.preference ? (
              <div
                style={{
                  border: "1.5px dashed var(--washi)",
                  borderRadius: 10,
                  padding: "10px 12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  animation: "rise .35s ease-out .2s both",
                }}
              >
                <span className="label" style={{ color: "var(--blush)" }}>
                  {result.new_preference ? "NEW NOTE FOR TOMORROW" : "ALREADY IN MY NOTES"}
                </span>
                <span style={{ fontWeight: 700, fontSize: 14 }}>{result.learned.preference}</span>
                {result.learned.applies_when && <span className="small" style={{ color: "var(--mist)" }}>When: {result.learned.applies_when}</span>}
              </div>
            ) : (
              <span className="small" style={{ color: "var(--mist)" }}>Nothing new to learn tonight. Today worked.</span>
            )}

            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="btn press block"
              onClick={onDone}
              style={{ background: "var(--washi)", color: "var(--sumi)", borderColor: "var(--washi)", boxShadow: "3px 3px 0 var(--shu)", height: 52 }}
            >
              Goodnight →
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function Question({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} style={{ display: "flex", flexDirection: "column", gap: 6, animation: "rise .35s ease-out both" }}>
      <span className="label" style={{ fontWeight: 400 }}>
        {n} / {title}
      </span>
      {children}
    </section>
  );
}
