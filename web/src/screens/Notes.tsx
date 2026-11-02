import { useEffect, useState } from "react";
import { api, type MaterialFamily, type Materials, type Preference, type Profile, type TryOnMode, type TryOnProfile } from "../api";
import type { AppCtx } from "../App";
import Oni, { MOOD_LABEL } from "../Oni";
import { getTheme, setTheme, type Theme } from "../theme";
import { AliveBar } from "./Today";
import { BasicsChecklist } from "./Touches";
import { QuizSheet, StyleDnaCard } from "./Taste";
import { DataNote } from "./Onboarding";

// The oni's notebook, in three tabs so nothing important hides under settings:
//   Your style    what it has learned (Style DNA), with the two quizzes that teach it right at the top
//   Your closet   closet alive, learned check-in rules, the basics you own but don't scan
//   Settings      setup, try-on, appearance, Today view, this closet's link

type Tab = "style" | "closet" | "settings";
const TABS: { id: Tab; en: string; ja: string }[] = [
  { id: "style", en: "Your style", ja: "好み" },
  { id: "closet", en: "Your closet", ja: "服" },
  { id: "settings", en: "Settings", ja: "設定" },
];

const TRYON_LABEL: Record<TryOnMode, string> = { mannequin: "Mannequin", photo: "My photo", flat: "Flat-lay only" };

export default function Notes({ ctx }: { ctx: AppCtx }) {
  const [prefs, setPrefs] = useState<Preference[] | null>(null);
  const [tryon, setTryon] = useState<TryOnProfile | null>(null);
  const [theme, setThemeState] = useState<Theme>(getTheme());
  const [setup, setSetup] = useState<Profile | null>(null);
  const [tab, setTab] = useState<Tab>("style");
  const [quiz, setQuiz] = useState<"styles" | "outfits" | null>(null);
  const [learned, setLearned] = useState(0); // bumps after a quiz round so Style DNA re-reads

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

      <section className="card" aria-label="The oni" style={{ padding: "10px 12px", display: "flex", gap: 12, alignItems: "center" }}>
        <Oni mood={mood} size={48} />
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <strong style={{ fontSize: 15 }}>
            {MOOD_LABEL[mood].en} <span lang="ja" style={{ fontWeight: 400, fontSize: 12 }}>{MOOD_LABEL[mood].ja}</span>
          </strong>
          <span className="small muted">
            {oni?.has_history ? `${oni.closet_alive_pct}% alive` : "No wear history yet"} · {oni?.forgotten ?? 0} forgotten · {oni?.streak_days ?? 0}-day streak
          </span>
        </span>
      </section>

      <TeachCard onPlay={setQuiz} />

      <div role="tablist" aria-label="Notes sections" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className="chip press"
            onClick={() => setTab(t.id)}
            style={{ height: 36, fontSize: 13, justifyContent: "center", ...(tab === t.id ? { background: "var(--sumi)", color: "var(--washi)" } : {}) }}
          >
            {t.en}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={TABS.find((t) => t.id === tab)!.en} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {tab === "style" && (
          <>
            <StyleDnaCard ctx={ctx} version={learned} onPlay={setQuiz} />
            {setup && <FabricsCard ctx={ctx} profile={setup} onSaved={setSetup} />}
          </>
        )}

        {tab === "closet" && (
          <>
            <section aria-label="Closet stats" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
                <Stat label="ALIVE" value={oni?.has_history ? `${oni.closet_alive_pct}%` : "—"} />
                <Stat label="FORGOTTEN" value={String(oni?.forgotten ?? 0)} shu={(oni?.forgotten ?? 0) > 0} />
                <Stat label="STREAK" value={`${oni?.streak_days ?? 0}d`} />
              </div>
              {oni?.has_history && <AliveBar pct={oni.closet_alive_pct} />}
              <span className="small muted">Closet alive = pieces worn in the last 30 days. It sets the oni's mood. No guilt: one rescued piece flips it to Fed.</span>
            </section>

            <section aria-label="Learned preferences" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span className="label">LEARNED FROM YOUR CHECK-INS · <span lang="ja">学び</span></span>
              {prefs === null && <span className="small">Loading…</span>}
              {prefs?.length === 0 && <span className="small muted">Nothing yet. Check in tonight and the oni starts learning what works for you.</span>}
              {prefs?.map((p, i) => (
                <div key={p.id} className="card" style={{ padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start", animation: `rise .3s ease-out ${(0.05 * i).toFixed(2)}s both` }}>
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

            <BasicsChecklist ctx={ctx} />
          </>
        )}

        {tab === "settings" && (
          <>
            <SettingRow label={<>YOUR SETUP · <span lang="ja">設定</span></>} onClick={ctx.openSetup}
              title={setup?.location?.name ?? "Toronto (default)"}
              sub={setup ? { ics: `Calendar: ${setup.calendar_name ?? "your file"}`, link: `Calendar linked: ${setup.calendar_name ?? "live"} · stays up to date`, sample: "Demo calendar", none: "Just weather, no calendar" }[setup.calendar] : "…"} />
            <SettingRow label={<>TRY-ON · <span lang="ja">試着</span></>} onClick={ctx.openTryOnSetup}
              title={tryon ? TRYON_LABEL[tryon.mode] : "…"}
              sub={tryon?.mode === "mannequin" && tryon.body
                ? `${tryon.body.height_cm} cm · ${tryon.body.build} · ${tryon.body.silhouette}`
                : tryon?.mode === "photo" ? "Your checked photo. Deletable anytime." : tryon?.ready === false ? "Not set up yet" : "No body, just your real cutouts"} />
            {tryon?.mode === "mannequin" && tryon.ready && (
              <button
                type="button"
                className="chip press"
                style={{ alignSelf: "flex-start", height: 32, fontSize: 12, marginTop: -6 }}
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

            <Choice label={<>APPEARANCE · <span lang="ja">表示</span></>} value={theme}
              options={[["system", "System"], ["light", "Light"], ["dark", "Dark"]]}
              onChange={(t) => { setTheme(t as Theme); setThemeState(t as Theme); }} />
            <Choice label={<>TODAY VIEW · <span lang="ja">画面</span></>} value={ctx.view}
              options={[["simple", "Simple"], ["full", "Everything"]]}
              onChange={(v) => ctx.setView(v as "simple" | "full")} />

            <YourCloset ctx={ctx} />

            {ctx.health && (
              <span className="label muted" style={{ fontWeight: 400, textAlign: "center", marginTop: 6 }}>
                SERVER · {ctx.health.mode.toUpperCase()} MODE · {ctx.health.garments} GARMENTS · {ctx.health.scans} SCANS
              </span>
            )}
          </>
        )}
      </div>

      {quiz && (
        <QuizSheet
          kind={quiz}
          ctx={ctx}
          onClose={(saved) => {
            setQuiz(null);
            if (saved) {
              ctx.toast(`Learned from ${saved} pick${saved === 1 ? "" : "s"}.`);
              setLearned((n) => n + 1);
              setTab("style");
            }
          }}
        />
      )}
    </main>
  );
}

// The two ways to teach the oni your taste, at the top of Notes where they're easy to find.
function TeachCard({ onPlay }: { onPlay: (kind: "styles" | "outfits") => void }) {
  const tiles: { kind: "styles" | "outfits"; title: string; sub: string; ja: string }[] = [
    { kind: "styles", title: "Style boards", sub: "Which styles are you? Streetwear, academia, gothic…", ja: "スタイル" },
    { kind: "outfits", title: "My outfits", sub: "This or that, from your own closet", ja: "私の服" },
  ];
  return (
    <section aria-label="Teach the oni" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span className="label">TEACH THE ONI YOUR TASTE · <span lang="ja">教える</span></span>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, paddingRight: 3 }}>
        {tiles.map((t) => (
          <button
            key={t.kind}
            type="button"
            className="card press"
            onClick={() => onPlay(t.kind)}
            style={{ padding: "12px 12px 10px", display: "flex", flexDirection: "column", gap: 4, textAlign: "left", boxShadow: "3px 3px 0 var(--sumi)", ...(t.kind === "styles" ? { borderColor: "var(--shu)" } : {}) }}
          >
            <span lang="ja" className="label muted" style={{ fontSize: 9 }}>{t.ja}</span>
            <strong style={{ fontSize: 16 }}>{t.title} →</strong>
            <span className="small muted" style={{ lineHeight: 1.35 }}>{t.sub}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

const FABRICS: [MaterialFamily, string][] = [
  ["cotton", "Cotton"], ["denim", "Denim"], ["linen", "Linen"], ["wool", "Wool"],
  ["silk", "Silk & satin"], ["leather", "Leather & suede"], ["fleece", "Fleece"], ["synthetic", "Synthetics"],
];

// Fabrics you love or won't wear. One tap loves it, a second avoids it, a third clears it.
function FabricsCard({ ctx, profile, onSaved }: { ctx: AppCtx; profile: Profile; onSaved: (p: Profile) => void }) {
  const [m, setM] = useState<Materials>(profile.materials ?? { love: [], avoid: [] });
  const state = (f: MaterialFamily) => (m.avoid.includes(f) ? "avoid" : m.love.includes(f) ? "love" : "none");
  const cycle = (f: MaterialFamily) => {
    const next = { none: "love", love: "avoid", avoid: "none" }[state(f)];
    const love = m.love.filter((x) => x !== f).concat(next === "love" ? [f] : []);
    const avoid = m.avoid.filter((x) => x !== f).concat(next === "avoid" ? [f] : []);
    const prev = m;
    setM({ love, avoid });
    api.updateProfile({ materials: { love, avoid } }).then(onSaved).catch((e) => {
      setM(prev);
      ctx.toast((e as Error).message);
    });
  };
  const owned = profile.materials_owned ?? {};
  return (
    <section aria-label="Fabrics" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span className="label">FABRICS · <span lang="ja">素材</span></span>
      <span className="small muted">Tap once for one you love, twice for one you won't wear (itchy, sweaty, not for you).</span>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, paddingRight: 3 }}>
        {FABRICS.map(([f, name]) => {
          const s = state(f);
          return (
            <button
              key={f}
              type="button"
              className={`chip press${s === "avoid" ? " shu" : ""}`}
              aria-pressed={s === "love"}
              aria-label={`${name}: ${s === "love" ? "love" : s === "avoid" ? "won't wear" : "no preference"}`}
              onClick={() => cycle(f)}
              style={{ height: 34, fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, padding: "0 12px" }}
            >
              <span style={{ textDecoration: s === "avoid" ? "line-through" : undefined }}>
                {s === "love" ? "♥ " : s === "avoid" ? "✕ " : ""}{name}
              </span>
              <span style={{ fontSize: 11, opacity: 0.7 }}>{owned[f] ? owned[f] : ""}</span>
            </button>
          );
        })}
      </div>
      {(m.love.length > 0 || m.avoid.length > 0) && (
        <span className="small muted">New picks use this. To see it today, tap ↻ New picks on Today.</span>
      )}
    </section>
  );
}

function SettingRow({ label, title, sub, onClick }: { label: React.ReactNode; title: string; sub: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="card press"
      onClick={onClick}
      style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: 10, textAlign: "left", boxShadow: "3px 3px 0 var(--sumi)" }}
    >
      <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="label">{label}</span>
        <strong style={{ fontSize: 14 }}>{title}</strong>
        <span className="small muted">{sub}</span>
      </span>
      <span aria-hidden="true" style={{ fontWeight: 700 }}>Edit →</span>
    </button>
  );
}

function Choice({ label, value, options, onChange }: { label: React.ReactNode; value: string; options: [string, string][]; onChange: (v: string) => void }) {
  return (
    <section style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
      <span className="label">{label}</span>
      <div role="radiogroup" style={{ display: "flex", gap: 6 }}>
        {options.map(([v, text]) => (
          <button key={v} type="button" role="radio" aria-checked={value === v} className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={() => onChange(v)}>
            {text}
          </button>
        ))}
      </div>
    </section>
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
    <section aria-label="Your closet" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
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
