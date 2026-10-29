import { useCallback, useEffect, useState } from "react";
import { api, type Health, type Item, type Oni as OniState, type Plan, type WearResult } from "./api";
import Today from "./screens/Today";
import Closet from "./screens/Closet";
import Scan from "./screens/Scan";
import Notes from "./screens/Notes";
import Thrift from "./screens/Thrift";
import Worn from "./screens/Worn";
import Checkin from "./screens/Checkin";
import ItemSheet from "./screens/ItemSheet";
import TryOn from "./screens/TryOn";
import Onboarding from "./screens/Onboarding";
import Oni from "./Oni";
import { setView as saveView, viewFromUrl, type View } from "./view";

export type Tab = "today" | "closet" | "scan" | "thrift" | "notes";

type Overlay =
  | { kind: "worn"; result: WearResult; plan: Plan; lookIndex: number }
  | { kind: "checkin"; plan: Plan | null; lookIndex: number | null }
  | { kind: "item"; item: Item }
  | { kind: "tryon"; plan: Plan | null; lookIndex: number | null; setupOnly: boolean }
  | null;

export interface AppCtx {
  oni: OniState | null;
  health: Health | null;
  refreshOni: () => void;
  go: (tab: Tab) => void;
  openItem: (item: Item) => void;
  openCheckin: (plan: Plan | null, lookIndex: number | null) => void;
  showWorn: (result: WearResult, plan: Plan, lookIndex: number) => void;
  openTryOn: (plan: Plan, lookIndex: number) => void;
  openTryOnSetup: () => void;
  openSetup: () => void; // reopen getting started (from the location step) to change location or calendar
  toast: (msg: string) => void;
  wardrobeVersion: number;
  bumpWardrobe: () => void;
  refreshKey: number; // bumps whenever an overlay closes, so screens behind it can re-read settings
  view: View; // simple: one look, the rest under "More"; full: everything open, for judges and demos
  setView: (v: View) => void;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [oni, setOni] = useState<OniState | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [wardrobeVersion, setWardrobeVersion] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  // First run shows getting started instead of the tabs; "edit" reopens it from Notes.
  const [onboarding, setOnboarding] = useState<"checking" | "first" | "edit" | null>("checking");

  const [view, setView] = useState<View>(viewFromUrl);

  useEffect(() => {
    // "Open on another device" links carry ?closet=<id>: move this browser to that closet first.
    const url = new URL(window.location.href);
    const linked = url.searchParams.get("closet");
    if (linked) {
      url.searchParams.delete("closet");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
    (linked ? api.openCloset(linked).then(() => setToastMsg("Opened your closet on this device.")).catch((e) => setToastMsg((e as Error).message)) : Promise.resolve())
      .then(() => api.profile())
      .then((p) => setOnboarding(p.onboarded ? null : "first"))
      .catch(() => setOnboarding(null));
  }, []);

  const refreshOni = useCallback(() => {
    api.oni().then(setOni).catch(() => {});
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);
  useEffect(refreshOni, [refreshOni, wardrobeVersion]);

  useEffect(() => {
    if (!toastMsg) return;
    const t = setTimeout(() => setToastMsg(null), 3200);
    return () => clearTimeout(t);
  }, [toastMsg]);

  const ctx: AppCtx = {
    oni,
    health,
    refreshOni,
    go: (t) => {
      setTab(t);
      window.scrollTo({ top: 0 });
    },
    openItem: (item) => setOverlay({ kind: "item", item }),
    openCheckin: (plan, lookIndex) => setOverlay({ kind: "checkin", plan, lookIndex }),
    // The wear response carries the look without expanded items; take them from the plan.
    showWorn: (result, plan, lookIndex) =>
      setOverlay({ kind: "worn", result: { ...result, look: plan.looks[lookIndex] }, plan, lookIndex }),
    openTryOn: (plan, lookIndex) => setOverlay({ kind: "tryon", plan, lookIndex, setupOnly: false }),
    openTryOnSetup: () => setOverlay({ kind: "tryon", plan: null, lookIndex: null, setupOnly: true }),
    openSetup: () => setOnboarding("edit"),
    toast: setToastMsg,
    wardrobeVersion,
    bumpWardrobe: () => setWardrobeVersion((v) => v + 1),
    refreshKey,
    view,
    setView: (v) => {
      saveView(v);
      setView(v);
    },
  };

  const close = () => {
    setOverlay(null);
    setRefreshKey((k) => k + 1);
    refreshOni();
  };

  if (onboarding === "checking") {
    return (
      <div className="app" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Oni mood="calm" size={72} />
      </div>
    );
  }
  if (onboarding) {
    return (
      <div className="app">
        <Onboarding
          ctx={ctx}
          editing={onboarding === "edit"}
          onDone={() => {
            setOnboarding(null);
            setTab(onboarding === "edit" ? tab : "today");
            setWardrobeVersion((v) => v + 1); // reload Today with the new setup
            window.scrollTo({ top: 0 });
          }}
        />
        {toastMsg && (
          <div className="toast" role="status" style={{ bottom: 24 }}>
            {toastMsg}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="app">
      {tab === "today" && <Today ctx={ctx} />}
      {tab === "closet" && <Closet ctx={ctx} />}
      {tab === "scan" && <Scan ctx={ctx} />}
      {tab === "thrift" && <Thrift ctx={ctx} />}
      {tab === "notes" && <Notes ctx={ctx} />}

      <TabBar tab={tab} go={ctx.go} />

      {overlay?.kind === "worn" && (
        <Worn
          result={overlay.result}
          onDone={close}
          onCheckin={() => setOverlay({ kind: "checkin", plan: overlay.plan, lookIndex: overlay.lookIndex })}
        />
      )}
      {overlay?.kind === "checkin" && (
        <Checkin plan={overlay.plan} lookIndex={overlay.lookIndex} ctx={ctx} onDone={close} />
      )}
      {overlay?.kind === "item" && <ItemSheet item={overlay.item} ctx={ctx} onClose={close} />}
      {overlay?.kind === "tryon" && (
        <TryOn plan={overlay.plan} lookIndex={overlay.lookIndex} setupOnly={overlay.setupOnly} ctx={ctx} onClose={close} />
      )}

      {toastMsg && (
        <div className="toast" role="status">
          {toastMsg}
        </div>
      )}
    </div>
  );
}

const TABS: { id: Tab; en: string; ja: string; icon: JSX.Element }[] = [
  {
    id: "today",
    en: "TODAY",
    ja: "今日",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    ),
  },
  {
    id: "closet",
    en: "CLOSET",
    ja: "服",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M10 6a2 2 0 1 1 2 2v2l9 7H3l9-7" />
      </svg>
    ),
  },
  {
    id: "scan",
    en: "SCAN",
    ja: "撮る",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  {
    id: "thrift",
    en: "THRIFT",
    ja: "古着",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z" />
        <circle cx="7.5" cy="7.5" r="1.5" />
      </svg>
    ),
  },
  {
    id: "notes",
    en: "NOTES",
    ja: "記録",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M5 20V11M12 20V4M19 20v-6" />
      </svg>
    ),
  },
];

function TabBar({ tab, go }: { tab: Tab; go: (t: Tab) => void }) {
  return (
    <nav className="tabbar" aria-label="Main">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={"tab" + (t.id === "scan" ? " scan" : "")}
          aria-current={tab === t.id ? "page" : undefined}
          onClick={() => go(t.id)}
        >
          {t.icon}
          {t.en}
          <span className="ja" lang="ja">
            {t.ja}
          </span>
        </button>
      ))}
    </nav>
  );
}
