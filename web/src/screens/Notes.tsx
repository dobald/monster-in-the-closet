import { useEffect, useState } from "react";
import { api, type Preference } from "../api";
import type { AppCtx } from "../App";
import Oni, { MOOD_LABEL } from "../Oni";
import { AliveBar } from "./Today";

// The oni's notebook: its mood, the closet-alive meter, and every preference it has learned
// from check-ins, each one forgettable.

export default function Notes({ ctx }: { ctx: AppCtx }) {
  const [prefs, setPrefs] = useState<Preference[] | null>(null);

  useEffect(() => {
    api.preferences().then(setPrefs).catch(() => setPrefs([]));
  }, []);

  const forget = async (p: Preference) => {
    await api.forget(p.id).catch((e) => ctx.toast((e as Error).message));
    setPrefs((prefs ?? []).filter((x) => x.id !== p.id));
    ctx.toast("Forgotten.");
  };

  const oni = ctx.oni;
  const mood = oni?.mood ?? "calm";

  return (
    <main className="screen">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "stretch", borderBottom: "var(--line)", paddingBottom: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 className="display" style={{ fontSize: 56 }}>NOTES</h1>
          <span style={{ fontSize: 13, fontWeight: 500 }}>What the oni knows about you</span>
        </div>
        <span lang="ja" aria-hidden="true" className="vertical" style={{ fontSize: 22 }}>
          鬼の記録
        </span>
      </header>

      <section className="card" style={{ padding: 14, display: "flex", gap: 14, alignItems: "center" }}>
        <Oni mood={mood} size={90} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="display" style={{ fontSize: 22 }}>
            {MOOD_LABEL[mood].en.toUpperCase()} <span lang="ja" style={{ fontSize: 14 }}>{MOOD_LABEL[mood].ja}</span>
          </span>
          <span className="small">{MOOD_LABEL[mood].line}</span>
        </div>
      </section>

      <section aria-label="Closet stats" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
        <Stat label="ALIVE" value={`${oni?.closet_alive_pct ?? 0}%`} />
        <Stat label="FORGOTTEN" value={String(oni?.forgotten ?? 0)} shu={(oni?.forgotten ?? 0) > 0} />
        <Stat label="STREAK" value={`${oni?.streak_days ?? 0}d`} />
      </section>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <AliveBar pct={oni?.closet_alive_pct ?? 0} />
        <div className="label" style={{ display: "flex", justifyContent: "space-between", fontWeight: 400, fontSize: 9 }}>
          <span>RESTLESS</span>
          <span>CALM · 25%</span>
          <span>PROUD · 60%</span>
        </div>
        <span className="small muted">Closet alive = pieces worn in the last 30 days. It sets the oni's mood. No guilt: one rescued piece flips it to Fed.</span>
      </div>

      <section aria-label="Learned preferences" style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
        <span className="label">LEARNED FROM YOUR CHECK-INS</span>
        {prefs === null && <span className="small">Loading…</span>}
        {prefs?.length === 0 && (
          <div className="card" style={{ padding: 14, borderStyle: "dashed" }}>
            <span className="small">Nothing yet. Check in tonight and the oni starts learning what works for you.</span>
          </div>
        )}
        {prefs?.map((p, i) => (
          <div key={p.id} className="card" style={{ padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start", animation: `rise .3s ease-out ${(0.05 * i).toFixed(2)}s both` }}>
            <span className="label" style={{ color: "var(--shu)", paddingTop: 3 }}>{String(i + 1).padStart(2, "0")}</span>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3 }}>
              <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.4 }}>{p.text}</span>
              {p.applies_when && <span className="small muted">When: {p.applies_when.replace(/_/g, " ")}</span>}
            </div>
            <button type="button" className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={() => forget(p)} aria-label={`Forget: ${p.text}`}>
              Forget
            </button>
          </div>
        ))}
      </section>

      {ctx.health && (
        <span className="label muted" style={{ fontWeight: 400, textAlign: "center", marginTop: 10 }}>
          SERVER · {ctx.health.mode.toUpperCase()} MODE · {ctx.health.garments} GARMENTS · {ctx.health.scans} SCANS
        </span>
      )}
    </main>
  );
}

function Stat({ label, value, shu }: { label: string; value: string; shu?: boolean }) {
  return (
    <div className="card" style={{ borderRadius: 10, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 4, ...(shu ? { background: "var(--shu)", color: "#fff", borderColor: "var(--sumi)" } : {}) }}>
      <span className="label" style={{ fontSize: 9 }}>{label}</span>
      <span className="display" style={{ fontSize: 24 }}>{value}</span>
    </div>
  );
}
