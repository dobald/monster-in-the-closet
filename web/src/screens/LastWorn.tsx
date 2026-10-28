import { useEffect, useState } from "react";
import { api, itemName, type Item } from "../api";

// "When did you last wear this?" A brand-new closet looks freshly worn (nothing has a history),
// so nothing can be rescued and the closet-alive % means nothing. A rough answer per piece fixes
// that from day one. Answers are estimates: they never count as wears, and a logged wear wins.

export const BUCKETS: { label: string; days: number | null }[] = [
  { label: "Not sure", days: null },
  { label: "This week", days: 3 },
  { label: "This month", days: 15 },
  { label: "1–3 months ago", days: 60 },
  { label: "3–6 months ago", days: 135 },
  { label: "6–12 months ago", days: 270 },
  { label: "Over a year ago", days: 400 },
];

function daysAgo(iso: string): number {
  return Math.max(0, Math.round((Date.now() - new Date(iso + "T12:00:00").getTime()) / 86_400_000));
}

/** The bucket an item's current last-worn date falls into ("Not sure" if there is none). */
export function bucketFor(item: Item): number | null {
  if (!item.last_worn) return null;
  const d = daysAgo(item.last_worn);
  const b = BUCKETS.filter((x) => x.days !== null).reduce((best, x) => (Math.abs(x.days! - d) < Math.abs(best.days! - d) ? x : best));
  return b.days;
}

/** True when the item's date came from a real "Wear this", not an estimate. */
export const loggedWear = (item: Item) => !!item.last_worn && !item.worn_estimated;

export function LastWornSelect({ item, value, onChange }: { item: Item; value: number | null; onChange: (days: number | null) => void }) {
  if (loggedWear(item)) {
    return <span className="small" style={{ fontWeight: 700 }}>Worn {daysAgo(item.last_worn!) === 0 ? "today" : `${daysAgo(item.last_worn!)} days ago`} ✓</span>;
  }
  return (
    <select
      aria-label={`When did you last wear the ${itemName(item).toLowerCase()}?`}
      value={value === null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      style={{
        height: 34, borderRadius: 17, border: "var(--line)", background: value === null ? "var(--washi)" : "var(--sumi)",
        color: value === null ? "var(--sumi)" : "var(--washi)", padding: "0 10px", fontSize: 13, fontWeight: 700, maxWidth: "100%",
      }}
    >
      {BUCKETS.map((b) => (
        <option key={b.label} value={b.days === null ? "" : String(b.days)}>{b.label}</option>
      ))}
    </select>
  );
}

/** Every item with its own picker, plus "set the rest to…". Calls onSaved after saving. */
export function LastWornList({ items, cta, onSaved, onError }: {
  items: Item[]; cta: string; onSaved: (updated: Item[]) => void; onError: (msg: string) => void;
}) {
  const [values, setValues] = useState<Record<string, number | null>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues(Object.fromEntries(items.map((i) => [i.id, bucketFor(i)])));
  }, [items]);

  const editable = items.filter((i) => !loggedWear(i));
  const unanswered = editable.filter((i) => values[i.id] === null || values[i.id] === undefined).length;

  const fillRest = (days: number) =>
    setValues((v) => ({ ...v, ...Object.fromEntries(editable.filter((i) => v[i.id] == null).map((i) => [i.id, days])) }));

  const save = async () => {
    setSaving(true);
    try {
      const changed = editable.filter((i) => (values[i.id] ?? null) !== bucketFor(i));
      const updated = changed.length ? await api.setLastWorn(changed.map((i) => ({ id: i.id, days_ago: values[i.id] ?? null }))) : [];
      onSaved(updated);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {unanswered > 1 && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span className="label" style={{ fontWeight: 400 }}>SET THE REST TO</span>
          {BUCKETS.filter((b) => b.days !== null && b.days >= 60).map((b) => (
            <button key={b.label} type="button" className="chip press" style={{ height: 30, fontSize: 12, padding: "0 10px" }} onClick={() => fillRest(b.days!)}>
              {b.label.replace(" ago", "")}
            </button>
          ))}
        </div>
      )}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((it) => (
          <li key={it.id} className="card" style={{ display: "flex", alignItems: "center", gap: 10, padding: 8 }}>
            <span className="halftone" style={{ flex: "none", width: 52, height: 52, border: "var(--line)", borderRadius: 6, padding: 3 }}>
              <img className="cutout" src={it.cutout_url} alt="" />
            </span>
            <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 700, lineHeight: 1.25 }}>{itemName(it)}</span>
            <LastWornSelect item={it} value={values[it.id] ?? null} onChange={(d) => setValues({ ...values, [it.id]: d })} />
          </li>
        ))}
      </ul>
      <button type="button" className="btn primary press block" style={{ height: 52 }} disabled={saving} onClick={save}>
        {saving ? "Saving…" : cta}
      </button>
    </div>
  );
}
