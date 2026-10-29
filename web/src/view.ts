// How much Today shows. "simple" (the default) is one look and one button, with the finishing
// touches, colour read, adjust chips and agent trace folded under "More". "full" opens all of it
// and names the models at work: the view for judges and demos. Open the app with ?view=full (or
// ?view=simple) to switch; it's remembered per device, and storage failures fall back to simple.

export type View = "simple" | "full";
const KEY = "monster.view";

export function getView(): View {
  try {
    return localStorage.getItem(KEY) === "full" ? "full" : "simple";
  } catch {
    return "simple";
  }
}

export function setView(view: View): void {
  try {
    localStorage.setItem(KEY, view);
  } catch {
    /* not remembered, still applied for this visit */
  }
}

/** Read ?view= once at start-up and drop it from the address bar. */
export function viewFromUrl(): View {
  const url = new URL(window.location.href);
  const v = url.searchParams.get("view");
  if (v === "full" || v === "simple") {
    setView(v);
    url.searchParams.delete("view");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    return v;
  }
  return getView();
}
