// Appearance: follow the system, or force light/dark. Remembered per device; storage can be
// unavailable (private mode), so every read and write is guarded and "system" is the fallback.

export type Theme = "system" | "light" | "dark";
const KEY = "monster.theme";

export function getTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#1e1b19" : "#F3EEE5");
}

export function setTheme(theme: Theme): void {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    /* not remembered, still applied */
  }
  applyTheme(theme);
}

export function initTheme(): void {
  applyTheme(getTheme());
  // Keep the browser chrome colour in step when the system flips while we follow it.
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    if (getTheme() === "system") applyTheme("system");
  });
}
