import { useEffect, useState } from "react";
import { api, type Preference, type Profile, type TryOnMode, type TryOnProfile } from "../api";
import type { AppCtx } from "../App";
import Oni, { MOOD_LABEL } from "../Oni";
import { getTheme, setTheme, type Theme } from "../theme";
import { AliveBar } from "./Today";
import { BasicsChecklist } from "./Touches";
import { DataNote } from "./Onboarding";

// The oni's notebook: its mood, the closet-alive meter, try-on settings, and every preference
// it has learned from check-ins, each one forgettable.

const TRYON_LABEL: Record<TryOnMode, string> = { mannequin: "Mannequin", photo: "My photo", flat: "Flat-lay only" };

export default function Notes({ ctx }: { ctx: AppCtx }) {
  const [prefs, setPrefs] = useState<Preference[] | null>(null);
  const [tryon, setTryon] = useState<TryOnProfile | null>(null);
  const [theme, setThemeState] = useState<Theme>(getTheme());
  const [setup, setSetup] = useState<Profile | null>(null);

  useEffect(() => {
    api.preferences().then(setPrefs).catch(() => setPrefs([]));
  }, []);
  useEffect(() => {
    api.tryonProfile().then(setTryon).catch(() => {});
    api.profile().then(setSetup).catch(() => {});
  }, [ctx.refreshKey]);

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
        <Stat label="ALIVE" value={oni?.has_history ? `${oni.closet_alive_pct}%` : "—"} />
        <Stat label="FORGOTTEN" value={String(oni?.forgotten ?? 0)} shu={(oni?.forgotten ?? 0) > 0} />
        <Stat label="STREAK" value={`${oni?.streak_days ?? 0}d`} />
      </section>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {oni?.has_history && <AliveBar pct={oni.closet_alive_pct} />}
        <div className="label" style={{ display: "flex", justifyContent: "space-between", fontWeight: 400, fontSize: 9 }}>
          <span>RESTLESS</span>
          <span>CALM · 25%</span>
          <span>PROUD · 60%</span>
        </div>
        <span className="small muted">Closet alive = pieces worn in the last 30 days. It sets the oni's mood. No guilt: one rescued piece flips it to Fed.</span>
      </div>

      <button
        type="button"
        className="card press"
        onClick={ctx.openSetup}
        style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, textAlign: "left", boxShadow: "3px 3px 0 var(--sumi)" }}
      >
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          <span className="label">YOUR SETUP · <span lang="ja">設定</span></span>
          <strong style={{ fontSize: 14 }}>{setup?.location?.name ?? "Toronto (default)"}</strong>
          <span className="small muted">
            {setup ? { ics: `Calendar: ${setup.calendar_name ?? "your file"}`, sample: "Demo calendar", none: "Just weather, no calendar" }[setup.calendar] : "…"}
          </span>
        </span>
        <span aria-hidden="true" style={{ fontWeight: 700 }}>Edit →</span>
      </button>

      <button
        type="button"
        className="card press"
        onClick={ctx.openTryOnSetup}
        style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, textAlign: "left", boxShadow: "3px 3px 0 var(--sumi)" }}
      >
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          <span className="label">TRY-ON · <span lang="ja">試着</span></span>
          <strong style={{ fontSize: 14 }}>{tryon ? TRYON_LABEL[tryon.mode] : "…"}</strong>
          <span className="small muted">
            {tryon?.mode === "mannequin" && tryon.body
              ? `${tryon.body.height_cm} cm · ${tryon.body.build} · ${tryon.body.silhouette}`
              : tryon?.mode === "photo" ? "Your checked photo. Deletable anytime." : tryon?.ready === false ? "Not set up yet" : "No body, just your real cutouts"}
          </span>
        </span>
        <span aria-hidden="true" style={{ fontWeight: 700 }}>Edit →</span>
      </button>
      {tryon?.mode === "mannequin" && tryon.ready && (
        <button
          type="button"
          className="chip press"
          style={{ alignSelf: "flex-start", height: 32, fontSize: 12 }}
          onClick={async () => {
            try {
              const items = await api.wardrobe();
              const s = await api.tryonLayers(items.map((i) => i.id), true);
              const todo = s.layers.filter((l) => l.state === "pending").length;
              ctx.toast(!s.live ? "Dressing happens in live mode." : todo ? `Dressing ${todo} piece${todo === 1 ? "" : "s"} in the background (about 20s each).` : "Every piece is already dressed.");
            } catch (e) {
              ctx.toast((e as Error).message);
            }
          }}
        >
          Dress the mannequin with my whole closet
        </button>
      )}

      <section aria-label="Appearance" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span className="label">APPEARANCE · <span lang="ja">表示</span></span>
        <div role="radiogroup" aria-label="Appearance" style={{ display: "flex", gap: 6 }}>
          {(["system", "light", "dark"] as Theme[]).map((t) => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={theme === t}
              className="chip press"
              style={{ height: 30, fontSize: 12, padding: "0 10px" }}
              onClick={() => {
                setTheme(t);
                setThemeState(t);
              }}
            >
              {t === "system" ? "System" : t === "light" ? "Light" : "Dark"}
            </button>
          ))}
        </div>
      </section>

      <section aria-label="Today view" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span className="label">TODAY VIEW · <span lang="ja">画面</span></span>
        <div role="radiogroup" aria-label="Today view" style={{ display: "flex", gap: 6 }}>
          {(["simple", "full"] as const).map((v) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={ctx.view === v}
              className="chip press"
              style={{ height: 30, fontSize: 12, padding: "0 10px" }}
              onClick={() => ctx.setView(v)}
            >
              {v === "simple" ? "Simple" : "Everything"}
            </button>
          ))}
        </div>
      </section>

      <BasicsChecklist ctx={ctx} />

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

      <YourCloset ctx={ctx} />

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

// Where this closet lives and how to reach it from another device. On a shared server (one closet per
// device) the link is the only key to the closet, so it's shown only here, to its owner.
function YourCloset({ ctx }: { ctx: AppCtx }) {
  const [closet, setCloset] = useState<{ per_device: boolean; id: string } | null>(null);
  useEffect(() => {
    api.closet().then(setCloset).catch(() => {});
  }, []);
  if (!closet) return null;
  const link = `${window.location.origin}/?closet=${closet.id}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      ctx.toast("Link copied. Open it on your other device; keep it private, it opens your closet.");
    } catch {
      window.prompt("Copy this link and open it on your other device:", link);
    }
  };
  const startOver = async () => {
    if (!window.confirm("Start a new, empty closet on this device? Your current closet stays reachable through its link.")) return;
    try {
      await api.newCloset();
      window.location.reload();
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  };

  return (
    <section aria-label="Your closet" style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
      <span className="label">YOUR CLOSET · <span lang="ja">クローゼット</span></span>
      <DataNote />
      {closet.per_device && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button type="button" className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={copy}>
            Open on another device
          </button>
          <button type="button" className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={startOver}>
            Start a new closet
          </button>
        </div>
      )}
    </section>
  );
}
