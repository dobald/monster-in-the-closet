// Captures app screens for the demo video from a running demo-mode app.
// Run the "api-scratch" and "web" launch configs first (throwaway closet, no paid calls), then:
//   node scripts/capture.mjs [step...]
// Screens land in public/captures/<name>.png at 2x a 430x932 phone viewport.
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import path from "node:path";

const APP = process.env.APP_URL ?? "http://localhost:5173/";
const CHROME =
  process.env.CHROME ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = path.resolve("public/captures");
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  userDataDir: path.resolve("scripts/.profile"),
});
const page = (await browser.pages())[0] ?? (await browser.newPage());
await page.emulateMediaFeatures([
  { name: "prefers-color-scheme", value: "light" },
  { name: "prefers-reduced-motion", value: "reduce" },
]);
await page.evaluateOnNewDocument(() => localStorage.setItem("monster.theme", "light"));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Full-page shots hide the fixed tab bar (it would land mid-page); the video lays tabbar.png over them.
async function shot(name, { full = false } = {}) {
  await sleep(700);
  const hide = full && (await page.addStyleTag({ content: "nav.tabbar { display: none !important; }" }));
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: full });
  if (hide) await hide.evaluate((el) => el.remove());
  console.log("captured", name);
}

async function press(label) {
  await page.click(`[aria-label="${label}"]`);
  await sleep(1200);
}

async function buttons() {
  return page.$$eval("button, [role=option], [role=radio], a", (els) =>
    els.filter((e) => e.offsetParent !== null).map((e) => e.innerText.replace(/\s+/g, " ").trim()).filter(Boolean),
  );
}

async function click(text, { exact = false, timeout = 15000, optional = false } = {}) {
  if (optional) timeout = 1500;
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const ok = await page.evaluate(
      (text, exact) => {
        const els = [...document.querySelectorAll("button, [role=option], [role=radio], [role=tab], a, label")];
        const el = els.find((e) => {
          if (e.offsetParent === null || e.disabled) return false;
          const t = e.innerText.replace(/\s+/g, " ").trim();
          return exact ? t === text : t.includes(text);
        });
        if (!el) return false;
        el.scrollIntoView({ block: "center" });
        el.click();
        return true;
      },
      text,
      exact,
    );
    if (ok) {
      await sleep(500);
      return true;
    }
    await sleep(300);
  }
  if (optional) return false;
  console.log("visible buttons:", await buttons());
  throw new Error(`No clickable "${text}"`);
}

async function scrollTo(y) {
  await page.evaluate((y) => window.scrollTo(0, y), y);
  await sleep(300);
}

const steps = {
  async onboarding() {
    await page.goto(APP, { waitUntil: "networkidle0" });
    await shot("01-hello");
    await click("Let's get started");
    if (await page.$("input[placeholder^='Search your city']")) {
      await page.type("input[placeholder^='Search your city']", "Toronto");
      await click("Toronto, Ontario, Canada");
    }
    await click("Neither", { exact: true });
    await shot("02-weather");
    await click("Next →");
    await click("Use the demo calendar");
    await shot("03-day");
    console.log(await buttons());
    await click("Next →");
    await shot("04-closet-empty");
    if (await click("Try a sample closet", { optional: true })) await sleep(4000);
    await shot("05-closet-sample");
    console.log(await buttons());
    await click("Next →");
    await sleep(1500);
    await shot("06-history");
    // Guessing fills in last-worn dates and moves on by itself.
    if (!(await click("Not sure? Guess for me", { optional: true }))) await click("Next →");
    await sleep(2000);
    await shot("07-taste");
    for (const n of [1, 2, 2, 1, 2, 1]) {
      await page.click(`[aria-label="Board ${n}"]`);
      await sleep(900);
    }
    await sleep(2500);
    await shot("08-first-pick");
    await click("See my day →");
  },

  async tabs() {
    const tab = async (name) => {
      await page.click(`nav[aria-label="Main"] .tab:nth-child(${["TODAY", "CLOSET", "SCAN", "THRIFT", "NOTES"].indexOf(name) + 1})`);
      await sleep(2500);
      await scrollTo(0);
    };
    await page.goto(APP, { waitUntil: "networkidle0" });
    await sleep(4000);
    await shot("10-today");
    await shot("10-today-full", { full: true });
    console.log("today:", await buttons());
    const nav = await page.$("nav.tabbar");
    await nav.screenshot({ path: path.join(OUT, "tabbar.png") });
    await press("Next look");
    await shot("11-today-look2");
    await press("Next look");
    await shot("12-today-look3");
    await press("Previous look");
    await press("Previous look");
    await tab("CLOSET");
    await shot("20-closet");
    await shot("20-closet-full", { full: true });
    console.log("closet:", await buttons());
    await tab("SCAN");
    await shot("30-scan");
    console.log("scan:", await buttons());
    await tab("THRIFT");
    await shot("40-thrift");
    await shot("40-thrift-full", { full: true });
    console.log("thrift:", await buttons());
    await tab("NOTES");
    await shot("50-notes");
    await shot("50-notes-full", { full: true });
    console.log("notes:", await buttons());
  },

  // "Wear this" marks the look worn, so this runs last.
  async agent() {
    await page.goto(APP, { waitUntil: "networkidle0" });
    await sleep(4000);
    await click("Touches & tweaks");
    await shot("13-today-tweaks");
    await click("How the oni decided");
    await sleep(2500);
    await shot("14-trace");
    await page.goto(APP, { waitUntil: "networkidle0" });
    await sleep(4000);
    await click("Evening check-in");
    await sleep(2500);
    await shot("70-checkin");
    console.log("checkin:", await buttons());
    await page.goto(APP, { waitUntil: "networkidle0" });
    await sleep(4000);
    await click("Wear this →");
    await sleep(3000);
    await scrollTo(0);
    await shot("15-wore-it");
  },
};

const wanted = process.argv.slice(2);
try {
  for (const [name, run] of Object.entries(steps)) {
    if (wanted.length && !wanted.includes(name)) continue;
    await run();
  }
} finally {
  await browser.close();
}
