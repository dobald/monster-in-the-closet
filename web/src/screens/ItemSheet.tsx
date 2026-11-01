import { useRef, useState } from "react";
import { api, idleDays, itemName, type Category, type Item, type Tags } from "../api";
import type { AppCtx } from "../App";
import { bucketFor, LastWornSelect } from "./LastWorn";

// Item detail (wireframe 3a, trimmed): the picture (product shot or the real scan), its tags and wear history,
// a remove action, and three ways to correct a piece the AI got wrong: fix the tags by hand, ask the tagger
// again with a hint, or rescan it with a new photo (its wear history carries over).

const CATEGORIES: Category[] = ["top", "bottom", "dress", "outerwear", "shoes", "accessory", "other"];
const PATTERNS = ["solid", "striped", "checked", "floral", "graphic", "print", "other"];
const FORMALITY: [string, string][] = [["athleisure", "Sporty"], ["casual", "Casual"], ["smart_casual", "Smart casual"], ["business", "Business"], ["formal", "Formal"]];
const SEASONS = ["spring", "summer", "fall", "winter"];

type Mode = "view" | "fix" | "ask";

export default function ItemSheet({ item, ctx, onClose }: { item: Item; ctx: AppCtx; onClose: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [current, setCurrent] = useState(item);
  const [showScan, setShowScan] = useState(false);
  const [mode, setMode] = useState<Mode>("view");
  const [busy, setBusy] = useState<string | null>(null);
  const photo = useRef<HTMLInputElement>(null);
  const tidy = current.photo_url !== current.cutout_url;
  const t = current.tags;
  const idle = idleDays(current);

  const remove = async () => {
    try {
      await api.deleteItem(current.id);
      const id = current.id;
      ctx.toast(`${itemName(current)} removed from your closet.`, {
        label: "Undo",
        run: () => api.restoreItem(id).then(() => ctx.bumpWardrobe()).catch((e) => ctx.toast((e as Error).message)),
      });
      ctx.bumpWardrobe();
      onClose();
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  };

  // Every correction ends the same way: show the corrected piece and refresh the screens behind.
  const run = async (label: string, job: () => Promise<Item>, done: string) => {
    setBusy(label);
    try {
      const updated = await job();
      setCurrent(updated);
      setShowScan(false);
      setMode("view");
      ctx.bumpWardrobe();
      ctx.toast(updated.is_garment ? done : `${itemName(updated)} is hidden from your closet.`);
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const rows: [string, string][] = t
    ? [
        ["Category", t.category],
        ["Colour", [t.primary_color, ...t.secondary_colors].join(", ")],
        ["Fit", t.fit],
        ["Material", t.material_guess],
        ["Pattern", t.pattern],
        ["Formality", t.formality.replace("_", " ")],
        ["Seasons", t.seasons.join(", ")],
        ["Details", t.distinctive_details],
      ]
    : [];

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={itemName(current)} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button type="button" className="icon-btn press" aria-label="Close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
          <span className="label" style={{ fontWeight: 400 }}>
            {(t?.category ?? "ITEM").toUpperCase()} · {current.wear_count}× WORN
          </span>
        </div>

        <div className="halftone" style={{ position: "relative", height: 300, border: "var(--line)", borderRadius: 12, padding: 18 }}>
          <img className="cutout" src={showScan || !tidy ? current.cutout_url : current.photo_url} alt={itemName(current)} />
          {tidy && (
            <>
              <span className="label" title="Muse Image redrew your scan as a product photo; SAM cut it out. It is only used when its measured colour stays close to the scan's." style={{ position: "absolute", left: 10, bottom: 14, fontSize: 9, background: "var(--washi)", border: "var(--line)", borderRadius: 4, padding: "2px 6px" }}>
                {showScan ? "YOUR SCAN" : current.photo_drift != null ? `REDRAWN · ΔE ${current.photo_drift.toFixed(1)}` : "REDRAWN"}
              </span>
              <div role="radiogroup" aria-label="Picture" style={{ position: "absolute", right: 10, bottom: 10, display: "flex", gap: 6 }}>
                {([[false, "Photo"], [true, "My scan"]] as const).map(([scan, text]) => (
                  <button key={text} type="button" role="radio" aria-checked={showScan === scan} className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={() => setShowScan(scan)}>
                    {text}
                  </button>
                ))}
              </div>
            </>
          )}
          {idle >= 30 && (
            <span className="sticker" style={{ position: "absolute", top: 12, left: 10, fontSize: 12 }}>
              {idle}日 UNWORN
            </span>
          )}
          {busy && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,.25)", borderRadius: 12 }}>
              <span style={{ background: "var(--washi)", border: "var(--line)", borderRadius: 6, padding: "6px 12px", fontWeight: 700, fontSize: 13 }}>
                <span className="spinner-dots">{busy}</span>
              </span>
            </div>
          )}
        </div>

        {tidy ? (
          <span className="small" style={{ fontSize: 12, marginTop: -4 }}>
            Redrawn photo missing a detail?{" "}
            <button type="button" className="press" disabled={!!busy} style={{ border: 0, background: "none", padding: 0, textDecoration: "underline", fontSize: "inherit", color: "inherit", fontWeight: 700 }}
              onClick={() => run("Switching to your scan", () => api.choosePhoto(current.id, "scan"), "Showing your own scan from now on.")}>
              Use my scan
            </button>
            {" · "}
            <button type="button" className="press" disabled={!!busy} style={{ border: 0, background: "none", padding: 0, textDecoration: "underline", fontSize: "inherit", color: "inherit", fontWeight: 700 }}
              onClick={() => run("Starting a redraw", () => api.choosePhoto(current.id, "redraw"), "Redrawing it in the background (about 30 seconds), checked against your scan.")}>
              Redraw
            </button>
          </span>
        ) : null}

        <h1 className="display" style={{ fontSize: 30, lineHeight: 1.05 }}>{itemName(current)}</h1>
        <span className="small">
          {current.last_worn
            ? `${current.worn_estimated ? "Last worn around" : "Last worn"} ${new Date(current.last_worn + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
            : "No wear history yet"}
          {" · from "}
          {current.source}
          {current.user_edited ? " · fixed by you" : ""}
        </span>

        <div role="group" aria-label="Correct this piece" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span className="label" style={{ width: "100%", fontSize: 10 }}>WRONG? · <span lang="ja">直す</span></span>
          <button type="button" className="chip press" aria-pressed={mode === "fix"} disabled={!!busy} onClick={() => setMode(mode === "fix" ? "view" : "fix")}>
            ✎ Fix it
          </button>
          <button type="button" className="chip press" aria-pressed={mode === "ask"} disabled={!!busy} onClick={() => setMode(mode === "ask" ? "view" : "ask")}>
            ↻ Ask again
          </button>
          <button type="button" className="chip press" disabled={!!busy} onClick={() => photo.current?.click()}>
            Rescan photo
          </button>
          <input
            ref={photo}
            type="file"
            accept="image/*,.heic,.heif"
            capture="environment"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) run("Scanning the new photo", () => api.rescanItem(current.id, f), "Rescanned. Its wear history came along.");
            }}
          />
        </div>

        {mode === "fix" && t && (
          <FixForm tags={t} busy={!!busy} onCancel={() => setMode("view")}
            onSave={(changes) => run("Saving your fix", () => api.fixItem(current.id, changes), "Fixed. The oni will use your version.")} />
        )}
        {mode === "ask" && (
          <AskAgain busy={!!busy} onCancel={() => setMode("view")}
            onAsk={(hint) => run("Asking Muse Spark again", () => api.retagItem(current.id, hint), "Tagged again.")} />
        )}

        {mode === "view" && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="label" style={{ width: 80 }}>LAST WORN</span>
              <LastWornSelect
                item={current}
                value={bucketFor(current)}
                onChange={async (days) => {
                  try {
                    const [updated] = await api.setLastWorn([{ id: current.id, days_ago: days }]);
                    setCurrent(updated);
                    ctx.bumpWardrobe();
                  } catch (e) {
                    ctx.toast((e as Error).message);
                  }
                }}
              />
            </div>

            {t && (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="label" style={{ width: 80 }}>WARMTH</span>
                  <div role="img" aria-label={`Warmth ${t.warmth} of 5`} style={{ display: "flex", gap: 4, flex: 1 }}>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <span key={n} style={{ flex: 1, height: 10, borderRadius: 2, ...(n <= t.warmth ? { background: "var(--shu)" } : { border: "var(--line)" }) }} />
                    ))}
                  </div>
                </div>
                <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "80px 1fr", gap: "8px 10px", borderTop: "var(--line)", paddingTop: 10 }}>
                  {rows.map(([k, v]) => (
                    <div key={k} style={{ display: "contents" }}>
                      <dt className="label" style={{ paddingTop: 2 }}>{k}</dt>
                      <dd style={{ margin: 0, fontSize: 14, lineHeight: 1.4 }}>{v}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </>
        )}

        <div style={{ flex: 1 }} />
        {confirming ? (
          <div style={{ display: "flex", gap: 10, paddingRight: 3 }}>
            <button type="button" className="btn press" style={{ flex: 1 }} onClick={() => setConfirming(false)}>
              Keep it
            </button>
            <button type="button" className="btn shu press" style={{ flex: 1 }} onClick={remove}>
              Yes, remove
            </button>
          </div>
        ) : (
          <button type="button" className="btn press block" onClick={() => setConfirming(true)}>
            Not mine / remove from closet
          </button>
        )}
      </div>
    </div>
  );
}

const field = { display: "flex", alignItems: "center", minHeight: 42, padding: "0 12px", border: "var(--line)", borderRadius: 21, background: "var(--washi)" } as const;
const input = { flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent", fontSize: 15, color: "inherit" } as const;
const chip = { height: 30, fontSize: 12, padding: "0 10px" } as const;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span className="label" style={{ fontSize: 10 }}>{label}</span>
      {children}
    </div>
  );
}

function Text({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <Row label={label}>
      <label style={field}>
        <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>{label}</span>
        <input value={value} maxLength={160} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} style={input} />
      </label>
    </Row>
  );
}

// Fix the tags by hand. Only the fields that changed are sent, and they are kept through later rescans.
function FixForm({ tags, busy, onSave, onCancel }: { tags: Tags; busy: boolean; onSave: (changes: Partial<Tags>) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState<Tags>(tags);
  const set = <K extends keyof Tags>(k: K, v: Tags[K]) => setDraft({ ...draft, [k]: v });
  const changes = Object.fromEntries(
    (Object.keys(draft) as (keyof Tags)[]).filter((k) => JSON.stringify(draft[k]) !== JSON.stringify(tags[k])).map((k) => [k, draft[k]]),
  ) as Partial<Tags>;
  const dirty = Object.keys(changes).length > 0;

  return (
    <form
      style={{ display: "flex", flexDirection: "column", gap: 12, borderTop: "var(--line)", paddingTop: 10 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (dirty) onSave(changes);
      }}
    >
      <Text label="WHAT IS IT" value={draft.subtype} onChange={(v) => set("subtype", v)} placeholder="e.g. zip-up hoodie" />
      <Row label="TYPE">
        <div role="radiogroup" aria-label="Type" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {CATEGORIES.map((c) => (
            <button key={c} type="button" role="radio" aria-checked={draft.category === c} className="chip press" style={chip} onClick={() => set("category", c)}>
              {c === "outerwear" ? "layer" : c}
            </button>
          ))}
        </div>
      </Row>
      <Text label="COLOUR" value={draft.primary_color} onChange={(v) => set("primary_color", v)} placeholder="e.g. charcoal grey" />
      <Text label="FIT" value={draft.fit} onChange={(v) => set("fit", v)} placeholder="e.g. oversized, long sleeve" />
      <Row label="PATTERN">
        <div role="radiogroup" aria-label="Pattern" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {PATTERNS.map((p) => (
            <button key={p} type="button" role="radio" aria-checked={draft.pattern === p} className="chip press" style={chip} onClick={() => set("pattern", p)}>
              {p}
            </button>
          ))}
        </div>
      </Row>
      <Row label="HOW DRESSY">
        <div role="radiogroup" aria-label="How dressy" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {FORMALITY.map(([v, label]) => (
            <button key={v} type="button" role="radio" aria-checked={draft.formality === v} className="chip press" style={chip} onClick={() => set("formality", v)}>
              {label}
            </button>
          ))}
        </div>
      </Row>
      <Row label="WARMTH">
        <div role="radiogroup" aria-label="Warmth" style={{ display: "flex", gap: 6 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" role="radio" aria-checked={draft.warmth === n} className="chip press" style={{ ...chip, flex: 1 }} onClick={() => set("warmth", n)}>
              {n}
            </button>
          ))}
        </div>
      </Row>
      <Row label="SEASONS">
        <div role="group" aria-label="Seasons" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {SEASONS.map((s) => {
            const on = draft.seasons.includes(s);
            return (
              <button key={s} type="button" aria-pressed={on} className="chip press" style={chip}
                onClick={() => set("seasons", on ? draft.seasons.filter((x) => x !== s) : SEASONS.filter((x) => x === s || draft.seasons.includes(x)))}>
                {s}
              </button>
            );
          })}
        </div>
      </Row>
      <Text label="DETAILS" value={draft.distinctive_details} onChange={(v) => set("distinctive_details", v)} placeholder="logos, prints, buttons…" />
      <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
        <input type="checkbox" checked={!draft.is_garment} onChange={(e) => set("is_garment", !e.target.checked)} />
        This isn't clothing (hide it)
      </label>
      <div style={{ display: "flex", gap: 10 }}>
        <button type="button" className="btn press" style={{ flex: 1 }} onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary press" style={{ flex: 2 }} disabled={!dirty || busy || !draft.subtype.trim()}>
          Save fix
        </button>
      </div>
    </form>
  );
}

// Ask the tagger again about the same cutout, optionally saying what the piece really is.
function AskAgain({ busy, onAsk, onCancel }: { busy: boolean; onAsk: (hint: string) => void; onCancel: () => void }) {
  const [hint, setHint] = useState("");
  return (
    <form
      style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "var(--line)", paddingTop: 10 }}
      onSubmit={(e) => {
        e.preventDefault();
        onAsk(hint);
      }}
    >
      <span className="small">Muse Spark looks at this cutout again. Tell it what the piece really is and it will trust you on that.</span>
      <Text label="WHAT IS IT REALLY (OPTIONAL)" value={hint} onChange={setHint} placeholder="e.g. it's a hoodie, not a dress" />
      <span className="small muted" style={{ fontSize: 12 }}>If the cutout itself is wrong (two things merged, half missing), use Rescan photo instead.</span>
      <div style={{ display: "flex", gap: 10 }}>
        <button type="button" className="btn press" style={{ flex: 1 }} onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary press" style={{ flex: 2 }} disabled={busy}>Ask again ↻</button>
      </div>
    </form>
  );
}
