import { useState } from "react";
import type { Plan, TraceStep } from "../api";

// "How the oni decided": the planner agent's run, step by step. Which model did what, which tools
// it called and what came back, a glimpse of its reasoning, and every check and repair before the
// plan reached you. Steps replay one after another so the run reads like it happened.

const KIND: Record<TraceStep["kind"], { badge: string; color: string }> = {
  context: { badge: "読", color: "var(--sumi)" },
  model: { badge: "考", color: "var(--ai)" },
  tool: { badge: "道", color: "var(--sumi)" },
  check: { badge: "検", color: "var(--sumi)" },
  repair: { badge: "直", color: "var(--shu)" },
  rules: { badge: "規", color: "var(--sumi)" },
  done: { badge: "選", color: "var(--shu)" },
};
const KIND_EN: Record<TraceStep["kind"], string> = {
  context: "CONTEXT", model: "MODEL", tool: "TOOL CALL", check: "CHECK", repair: "REPAIR", rules: "RULES", done: "DONE",
};

export default function TraceSheet({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [run, setRun] = useState(0); // bump to replay the animation
  const t = plan.trace;
  const steps = t.steps ?? [];
  const model = plan.source === "rules" ? "Rule picker" : (t.model ?? t.provider ?? "").replace("meta-models/", "");

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="How the oni decided" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <button type="button" className="chip press" style={{ height: 32, fontSize: 12 }} onClick={() => setRun(run + 1)}>
            Replay ↻
          </button>
        </div>

        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 10 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h1 className="display" style={{ fontSize: "clamp(30px, 10vw, 40px)", lineHeight: 0.95 }}>HOW THE ONI DECIDED</h1>
            <span className="small">Every plan is checked against your real closet before you see it.</span>
          </div>
          <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 20 }}>判断</span>
        </header>

        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span className="tag-ai">{model.toUpperCase()}</span>
          {t.seconds ? <span className="label" style={{ border: "var(--line)", borderRadius: 4, padding: "3px 6px" }}>{t.seconds}S</span> : null}
          {t.tokens_in ? <span className="label" style={{ border: "var(--line)", borderRadius: 4, padding: "3px 6px" }}>{t.tokens_in.toLocaleString()} IN · {(t.tokens_out ?? 0).toLocaleString()} OUT</span> : null}
          {t.repairs ? <span className="sticker" style={{ transform: "none" }}>{t.repairs} REPAIR</span> : null}
          {t.cached || plan.source === "cache" ? <span className="label" style={{ border: "var(--line)", borderRadius: 4, padding: "3px 6px" }}>REPLAYED FROM CACHE</span> : null}
        </div>

        {steps.length === 0 ? (
          <p className="small">This plan was made before traces were recorded. Ask for a fresh pick to see one.</p>
        ) : (
          <ol key={run} style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column" }}>
            {steps.map((s, i) => {
              const k = KIND[s.kind] ?? KIND.context;
              const failed = s.ok === false;
              return (
                <li
                  key={i}
                  style={{ display: "grid", gridTemplateColumns: "36px 1fr", gap: 10, animation: `rise .35s ease-out ${i * 0.32}s both` }}
                >
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <span
                      lang="ja"
                      aria-hidden="true"
                      style={{
                        width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                        fontFamily: "var(--display)", fontSize: 15, flex: "none",
                        ...(s.kind === "done" || failed || s.kind === "repair"
                          ? { background: failed ? "var(--shu)" : "var(--washi)", color: failed ? "#fff" : "var(--shu)", border: "2px solid var(--shu)" }
                          : { border: "var(--line)", color: k.color, background: "var(--washi)" }),
                      }}
                    >
                      {failed ? "✕" : k.badge}
                    </span>
                    {i < steps.length - 1 && <span aria-hidden="true" style={{ flex: 1, width: 0, borderLeft: "1.5px dashed var(--ghost)", minHeight: 14 }} />}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 3, paddingBottom: 14 }}>
                    <span style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
                      <span className="label" style={{ fontSize: 9, color: failed ? "var(--shu)" : undefined }}>
                        {KIND_EN[s.kind] ?? s.kind.toUpperCase()}
                        {s.kind === "check" && s.ok !== undefined ? (s.ok ? " · PASSED" : " · FAILED") : ""}
                      </span>
                      {!!s.ms && s.kind !== "done" && (
                        <span className="label muted" style={{ fontWeight: 400, fontSize: 9 }}>
                          {s.ms >= 1000 ? `${(s.ms / 1000).toFixed(1)}S` : `${s.ms}MS`}
                          {s.tokens ? ` · ${s.tokens} TOK` : ""}
                        </span>
                      )}
                    </span>
                    <strong style={{ fontSize: 14, lineHeight: 1.3, fontFamily: s.kind === "tool" ? "var(--mono)" : undefined }}>{s.label}</strong>
                    {s.detail && <span className="small" style={{ lineHeight: 1.45 }}>{s.detail}</span>}
                    {s.thought && (
                      <span
                        className="small"
                        style={{ borderLeft: "3px solid var(--ai)", padding: "4px 8px", background: "var(--paper)", borderRadius: "0 6px 6px 0", fontStyle: "italic" }}
                      >
                        <span className="label" style={{ fontStyle: "normal", fontSize: 9, display: "block", color: "var(--ai)" }}>THINKING</span>
                        {s.thought}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        {t.failures && t.failures.length > 0 && (
          <span className="small muted">Fallbacks used: {t.failures.join(" · ")}</span>
        )}
        <div style={{ flex: 1 }} />
        <button type="button" className="btn primary press block" onClick={onClose}>
          Back to today
        </button>
      </div>
    </div>
  );
}
