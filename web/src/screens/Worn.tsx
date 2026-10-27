import type { WearResult } from "../api";
import { shortName } from "../api";
import Oni from "../Oni";
import { AliveBar } from "./Today";

// The payoff: confetti, a bouncing oni and the 救 ("rescued") stamp when a forgotten piece goes back out.

const CONFETTI = ["#C4472F", "#34506B", "#2B2724", "#E8E1D4"];

function burstPolygon(): string {
  const pts: string[] = [];
  for (let i = 0; i < 32; i++) {
    const a = (Math.PI * 2 * i) / 32;
    const r = i % 2 === 0 ? 50 : 40;
    pts.push(`${(50 + r * Math.cos(a)).toFixed(1)}% ${(50 + r * Math.sin(a)).toFixed(1)}%`);
  }
  return `polygon(${pts.join(", ")})`;
}

export default function Worn({ result, onDone, onCheckin }: { result: WearResult; onDone: () => void; onCheckin: () => void }) {
  const rescued = result.rescued[0];
  const delta = result.closet_alive_after - result.closet_alive_before;
  const hero = result.look.items.find((i) => i.id === rescued?.id) ?? result.look.items[0];
  const time = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Outfit logged">
      <div className="sheet" style={{ overflow: "hidden" }}>
        <div aria-hidden="true" style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 4 }}>
          {Array.from({ length: 18 }, (_, i) => {
            const w = 6 + (i % 3) * 3;
            return (
              <span
                key={i}
                style={{
                  position: "absolute",
                  top: 0,
                  left: `${(i * 23 + 7) % 100}%`,
                  width: w,
                  height: Math.round(w * 1.8),
                  background: CONFETTI[i % 4],
                  border: "1px solid var(--sumi)",
                  borderRadius: 1,
                  animation: `fall ${(2.4 + (i % 5) * 0.35).toFixed(2)}s linear ${(0.08 * i).toFixed(2)}s 1 both`,
                }}
              />
            );
          })}
        </div>

        <div style={{ position: "relative", zIndex: 2, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onDone}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            {result.look.name.toUpperCase()} · WORN {time}
          </span>
        </div>

        <div aria-hidden="true" style={{ position: "relative", height: 230, width: 270, margin: "0 auto" }}>
          <span
            style={{
              position: "absolute",
              left: -10,
              top: -30,
              width: 280,
              height: 280,
              background: "var(--ai)",
              clipPath: burstPolygon(),
              animation: "spin 40s linear infinite",
            }}
          />
          <span style={{ position: "absolute", left: 56, top: 30 }}>
            <Oni mood="fed" size={140} />
          </span>
          {hero && (
            <span
              className="halftone"
              style={{
                position: "absolute",
                right: 0,
                bottom: 0,
                width: 86,
                height: 104,
                border: "var(--line)",
                borderRadius: 6,
                overflow: "hidden",
                transform: "rotate(10deg)",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <img className="cutout" src={hero.cutout_url} alt="" style={{ flex: 1, minHeight: 0, padding: 4 }} />
              <span style={{ background: "var(--washi)", borderTop: "var(--line)", padding: "2px 5px", fontSize: 10, fontWeight: 700 }}>{shortName(hero)}</span>
            </span>
          )}
          {rescued && (
            <span
              lang="ja"
              className="hanko"
              style={{ position: "absolute", right: 46, bottom: 56, border: "3px solid var(--shu)", background: "rgba(243,238,229,.85)", fontSize: 26, animation: "stamp .5s cubic-bezier(.2,.9,.3,1.2) .6s both" }}
            >
              救
            </span>
          )}
        </div>

        <header style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: 4, animation: "rise .4s ease-out .2s both" }}>
          <h1 className="display" style={{ fontSize: 50 }}>{rescued ? "RESCUED!" : "WORN IT!"}</h1>
          {rescued ? (
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {rescued.name.charAt(0).toUpperCase() + rescued.name.slice(1)} is back after{" "}
              <span style={{ background: "var(--shu)", color: "#fff", borderRadius: 3, padding: "0 5px" }}>{rescued.days} days</span>.
            </span>
          ) : (
            <span style={{ fontSize: 15, fontWeight: 700 }}>Logged. Every wear keeps your closet alive.</span>
          )}
          <span lang="ja" style={{ fontSize: 12, fontWeight: 500 }}>
            {rescued ? "救出成功 · the oni is full and happy" : "着用記録 · the oni is pleased"}
          </span>
        </header>

        <section aria-label="Progress" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8, animation: "rise .4s ease-out .4s both" }}>
          <div className="card" style={{ borderRadius: 10, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="label" style={{ fontSize: 9 }}>CLOSET ALIVE</span>
            <span className="display" style={{ fontSize: 20 }}>
              {result.closet_alive_after}%{" "}
              {delta > 0 && <span className="label" style={{ fontSize: 11 }}>▲{delta}</span>}
            </span>
            <AliveBar pct={result.closet_alive_after} from={result.closet_alive_before} />
          </div>
          <div className="card" style={{ borderRadius: 10, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="label" style={{ fontSize: 9 }}>WEAR STREAK</span>
            <span className="display" style={{ fontSize: 20 }}>
              {result.streak_days} {result.streak_days === 1 ? "day" : "days"}
            </span>
            <div role="img" aria-label={`${Math.min(result.streak_days, 7)} of 7 days`} style={{ display: "flex", gap: 4 }}>
              {Array.from({ length: 7 }, (_, i) => (
                <span
                  key={i}
                  style={{
                    flex: 1,
                    height: 10,
                    borderRadius: 2,
                    ...(i < result.streak_days ? { background: "var(--shu)" } : { border: "var(--line)" }),
                  }}
                />
              ))}
            </div>
          </div>
        </section>

        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
          <button type="button" className="btn press" style={{ flex: 1 }} onClick={onDone}>
            Done
          </button>
          <button type="button" className="btn primary press" style={{ flex: 2 }} onClick={onCheckin}>
            Check in tonight →
          </button>
        </div>
      </div>
    </div>
  );
}
