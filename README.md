# Monster in the Closet

> It noticed I haven't worn 60% of my closet and dressed me in it for today, without me asking.

A closet-first morning agent:
1. Lay 4–8 items flat and snap one photo per batch.
2. **SAM 3.1** cuts out every garment, and **Muse Spark** catalogs each one.
3. Each morning, the agent picks an outfit from clothes you already own. It takes the weather and your calendar into account and favours pieces you've forgotten about.

Built for the **Meta Global AI Developer Hackathon** (Indie track, *Build for Your World*).

## Built during the hackathon

Everything in this repository was written during the hackathon (Oct 26 – Nov 4, 2026), starting from an empty folder. The commit history is the record.

## Meta models used

| Model | Role |
|---|---|
| SAM 3.1 | Cuts every garment out of a flat-lay photo with one "clothing" prompt. |
| Muse Spark 1.3 | Tags each item with structured output and checks render fidelity. |
| Muse Image | Optional try-on on a faceless mannequin (default) or your own photo (opt-in). |
| Muse Voice Transcribe | Voice tweaks: "nothing black, dinner outside" *(planned)* |
| Muse Spark Open (via Baseten) | Open-weights brain: outfit planning, check-in learning, Ask *(in progress)* |

## Day-0 findings (real closet, ~$1.60 total)

| Capture | Garments found | Usable cutouts | Time |
|---|---|---|---|
| Rail pan video, 19s, 9 prompts | ~14 tracked | 5 of 25 (edge slivers) | ~27 min, 5 prompts failed |
| Flick-through video, 46s, 1 prompt | 16 tracked | 9 of 16 | 39 min |
| **Flat-lay photo, 1 prompt** | **4 of 4** | **4 of 4, tags all correct** | **~15s** |

So the scan flow is flat-lay photo batches. Other findings:
- **Prompts:** "clothing" alone finds everything; noun prompts only add duplicates.
- **Speed:** segmenting a 1024px copy is ~3× faster than 2048px. Masks are upscaled, so cutouts stay full resolution.
- **Tagging:** Spark 1.3 beat Spark Open on crumpled cutouts. Spark Open called tops "shoes" and is 4× slower, so it now handles text reasoning instead.
- **Try-on:**
  - Mannequin renders keep prints and logos well.
  - **Tag-aware renders.** Tagging records each item's fit and which side its print is on, and the try-on prompt uses both.
    - The tour tee's back print came back: pattern fidelity went from 1/5 to 5/5 on the person and from 3/5 to 5/5 on the mannequin.
    - Baggy jeans stopped being slimmed: cut went from 2/5 to 4/5.
  - **Render pipeline:**
    1. **Measured colour.** The prompt gets each garment's real colour, measured from the photo. The jeans' wash went from 2/5 to 4/5.
    2. **Content-filter fallback.** On a refusal, item details are shortened before body details are dropped. The tee mannequin now keeps its height and build.
    3. **Self-correction.** A render scoring under 4/5 is redone once with the judge's corrections, and the better attempt is kept. One outfit went from 3/5 to 4/5, and keeping the better attempt stopped a worse retry from replacing the first.
    4. **Photo check for the face version.** It rejects photos where the face is hidden and asks for a retake, instead of letting Muse Image invent a face.
    5. **Calibrated judge.** One Spark 1.3 review covers the whole render: every garment, plus the wearer judged once.
       - It scores on an explicit 1–5 scale and is told which view was requested.
       - It doesn't judge mannequin height.
       - It treats a featureless head as correct and a changed fit as a 2.
       - Results on saved renders: good ones now score 4–5 (the old judge gave good mannequins 1–2), bad ones still score 1–2, and repeat runs gave the same score.
  - **Known limits:**
    - Micro-text (tour dates) blurs in any generated render; the flat-lay stays the faithful view.
    - Muse Image wouldn't draw a truly headless mannequin, so the only mannequin is the faceless one.
  - The face version needs a clear photo, or Muse Image invents a face.
  - Body-detail wording can trip Muse Image's content filter, so the prompt falls back to simpler wording.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # then add MODEL_API_KEY
```

## Backend API

```bash
uvicorn server.main:app --reload                       # fixture mode (default): never calls a paid API
MONSTER_MODE=live uvicorn server.main:app --reload     # live: SAM 3.1 + Muse Spark, every result cached
```

Docs: http://127.0.0.1:8000/docs

| Endpoint | What it does |
|---|---|
| `POST /api/scans` | 1–10 flat-lay photos (JPEG/PNG/WebP/HEIC) → cutouts → tags → wardrobe |
| `GET /api/scans/{id}` | A past scan and its items |
| `GET /api/wardrobe` | Garments; filter with `?category=top`, `?include_hidden=true` |
| `GET` / `PATCH` / `DELETE /api/wardrobe/{id}` | One item; `PATCH` is "Fix tags", and later rescans keep those fixes |
| `GET /api/cutouts/{id}.png` | The garment cutout |
| `POST /api/dev/seed` | Import a spike run (`{"run": "out/<run>"}`) as wardrobe items and fixtures |

**Spend-safe by design:**
- **Content-addressed cache.** Every SAM scan and every tag is cached under a hash of its input plus a version string. A repeated photo costs nothing: the same scan took 29.5s live, then 0.1s from cache.
- **Automatic invalidation.** Changing the tag schema or the scan settings invalidates old entries.
- **Fixture mode.** It serves only recorded results. An unseen photo replays a recorded scan, so front-end work never spends credits.
- **No duplicates.** Item ids are hashes of the cutout, so the same garment scanned twice is stored once. Wear history and tag fixes survive a rescan.
- **Local data stays local.** The database, cutouts and cache live in `var/`, which git ignores.

Tests (no API calls): `python tests/test_server.py` and `python tests/test_offline.py`

## Morning planner and evening check-in

The oni's brain runs on **Muse Spark Open via Baseten** as a small tool-using agent:

1. It gets the wardrobe as compact text lines (tags, warmth, last worn), plus preferences learned from past check-ins.
2. It calls two tools:
   - `get_weather`: Open-Meteo, free, no key. Summarised into morning, afternoon and evening, using feels-like temperatures.
   - `get_calendar`: a JSON or ICS file.
3. It returns three looks in a fixed schema.
4. Every look is checked against the real wardrobe for invented ids, missing bottoms and repeated items. One repair round fixes problems. The repair round also asks for variety when all three looks share a top, but variety alone never fails a plan.
5. Fallbacks: if Spark Open fails, the same agent runs on Muse Spark 1.3; if that fails too, a rule-based picker answers. Fixture mode always uses the rules, so the morning screen never breaks and never spends credits.

| Endpoint | What it does |
|---|---|
| `POST /api/plan` | Today's three looks. Body (all optional): `day`, `notes` (e.g. "nothing black"), `lat`/`lon`, `fresh` |
| `GET /api/plan?day=` | The latest plan for a day |
| `POST /api/plans/{id}/wear` | "Wear this" (`{"look": 0}`). Returns rescued pieces (idle ≥30 days), the closet-alive % before and after, the streak and the oni's mood |
| `POST /api/checkins` | Evening check-in: `temperature` (cold, just_right, warm), `feeling` (meh, fine, good, iconic), `tags`, `note`. The oni replies and may learn one preference |
| `GET /api/preferences`, `DELETE /api/preferences/{id}` | What the oni has learned; the user can make it forget |
| `GET /api/oni` | Mood (restless, calm, proud, fed, sleepy), closet-alive %, forgotten count, streak |

Plans are cached under a hash of everything they depend on: wardrobe and wear state, preferences, weather, calendar, notes and day. Asking twice is free, and wearing an outfit or learning a preference naturally produces a new plan.

**Live run (11-garment closet, Toronto, feels like −2° in the morning, a smart-casual crit and a patio dinner):**
- Spark Open called both tools and returned a valid plan in 9–20s, using about 5–7k tokens in and 2–5k out. 20s is the run with a repair round.
- A "nothing black" note was respected.
- A "studio was boiling" check-in was learned as "runs warm indoors". The next plan picked lighter tops for the studio.
- An identical repeat request came from the cache in 0.0s.
- Spark Open ignores field descriptions in the JSON schema, so length and voice rules (no ids, no "3/5", no raw temperatures) are spelled out in the prompt.

Settings in `.env`:
- `PLAN_PROVIDER`: `baseten` (default) or `meta`
- `MONSTER_LAT` and `MONSTER_LON`: default location, Toronto
- `MONSTER_CALENDAR`: JSON or ICS path; defaults to `fixtures/calendar_sample.json`

## Front end (mobile web)

React + Vite in `web/`, styled after the Tokyo-street wireframes (washi, sumi, shu for the oni, ai for your day). Run the API and the dev server side by side; Vite proxies `/api` to port 8000:

```bash
uvicorn server.main:app --reload        # terminal 1 (add MONSTER_MODE=live for real model calls)
cd web && npm install && npm run dev    # terminal 2 → http://localhost:5173
```

Screens:
- **Today:** the oni's three looks as a cutout collage on riso halftone, with weather and calendar on a ticker. Chips (Warmer, Dressier, No black) re-plan with notes.
- **Worn it!:** confetti, the fed oni, the 救 stamp for rescued pieces, closet-alive change and streak.
- **Evening check-in:** temperature, feeling, tags and a note; shows the oni's reply and what it learned.
- **Closet:** a searchable, filterable pinboard grid, with an item sheet showing tags and a remove action.
- **Scan:** pick 1–10 flat-lay photos and build the closet.
- **Notes:** the oni's mood, closet-alive meter and every learned preference. Each preference can be forgotten.

In fixture mode the Today screen shows a DEMO DATA tag, and plans come from the rule picker.

## Day-0 spike

A go/no-go test on real photos. Put your media in `data/`, which git ignores. iPhone HEIC photos work.

```bash
python spike/spike.py all data/batch1.heic data/batch2.heic --expected 10 --dry-run   # cost estimate
python spike/spike.py all data/batch1.heic data/batch2.heic --expected 10
```

Each run writes to `out/<timestamp>/`:
- `SUMMARY.md`: pass/fail on segmentation, double-counting and render fidelity
- `contact_sheet.png` and `cutouts/`: every garment SAM found
- `wardrobe.json`: Muse Spark's tags
- `render_mannequin.png` and `flatlay.png`: the try-on next to the always-faithful flat-lay

Steps on their own:
- `scan`: photos (the main path)
- `tag`
- `render`
- `segment`: optional, slow video inventory

`spike/compare_tags.py` runs the Spark Open vs Spark 1.3 comparison. `spike/smoke_meta.py` and `spike/smoke_baseten.py` check the keys.

Offline self-test (no API calls): `python tests/test_offline.py`

## Privacy

- **No photo of you is needed.** Try-on has three modes:
  - **Mannequin** (default): a faceless stand-in built from height, build, form and a finish colour.
  - **My photo** (opt-in): the face version.
  - **Flat-lay only:** your real cutouts, no body at all.
- **What leaves your device:**
  - **Closet photos → Meta, for SAM segmentation.** The optional video path deletes the upload from Meta's file storage as soon as segmentation finishes.
  - **Garment cutouts → Meta (Muse Spark 1.3), for tagging.**
  - **Text only → Baseten (Muse Spark Open), for the morning plan and check-ins.** This is garment tags, today's weather, calendar event titles and times, and check-in answers. No images.
  - **Renders → Meta's Muse Image.** This includes your photo only if you chose the face version.
- **Never sent to Meta's "contributor" models,** which may use inputs for training.
- **Local files stay out of git.** Closet footage, selfies and renders live in `data/` and `out/`. Both folders are git-ignored and never committed. This repo is public.

Spike try-on examples:

```bash
python spike/spike.py render out/<run> --height 165 --build curvy --silhouette feminine --skin 5   # mannequin
python spike/spike.py render out/<run> --person data/me.jpg                                        # face version
```

## Layout

```
closet/       shared code: config + provider routing, schema, SAM client, scan flow, media, models,
              planner agent + weather/calendar tools
server/       FastAPI backend: settings, cache, SQLite store, scan pipeline, planning, routes
fixtures/     sample calendar for the planner
web/          mobile web front end (React + Vite)
spike/        Day-0 go/no-go scripts and bake-offs
tests/        offline tests (no API calls)
data/ out/ var/   local only (ignored): footage, spike runs, the dev database and cache
```
