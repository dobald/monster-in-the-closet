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

**Same garment, different photos.** Item ids hash the cutout, so one hoodie shot in two batches used to become two items. Every scan, and the Closet's "Find duplicates" button, now runs a cross-photo check:
1. **Shortlist pairs cheaply:** compatible categories and a close measured colour (ΔE ≤ 20). On the real 11-item test closet this left 13 pairs.
2. **Judge each pair:** Muse Spark 1.3 looks at both cutouts and writes down matching and conflicting details before giving a verdict. Verdicts are cached per pair.
3. **Act on the verdict:**
   - At confidence ≥ 0.85 the two items merge. The cutout that shows the most garment is kept, wear history moves over, and the other cutout id becomes an alias, so a rescan doesn't bring it back.
   - Less certain matches become "same item?" cards for the user to decide.
   - "Different" is remembered, so that pair is never asked again.

On the test closet the judge was 13/13 right in about 10s:
- the black sweatshirt shot twice, the tour tee shot twice, and the track pants shot three times all merged (confidence 0.88–0.96)
- the white henley was kept separate from the white tour tee (0.99)
- the closet went from 11 items to 7

| Endpoint | What it does |
|---|---|
| `POST /api/wardrobe/duplicates/check` | Run the check over the closet: confident pairs merge; returns `merged` and `review` |
| `POST /api/wardrobe/duplicates/merge` | `{a, b}`: the user confirmed one garment |
| `POST /api/wardrobe/duplicates/distinct` | `{a, b}`: the user says these are different; never suggest again |

Scan responses carry the same `duplicates` block for the items that scan added.

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

**"How the oni decided": the visible agent trace.** Every plan records each step of the run, and Today shows it as a timeline. Live, one run on Muse Spark Open (14.5s, 4.3k tokens in / 3.5k out) looked like this:
1. **Reads your closet:** 7 garments, 6 with wear history, 2 learned preferences.
2. **Muse Spark Open plans its next move:** calls `get_weather()` and `get_calendar()`. A short excerpt of its reasoning is shown; Baseten returns `reasoning_content`.
3. **The tools return:** "7–15°C, feels like 4° at the coldest" and "10:00 Studio crit (smart casual), 19:00 Dinner outside".
4. **Writes the plan as structured output:** three named looks.
5. **Checks every look against your real closet:** all item ids exist, and every look has a top and a bottom.
6. **Plan ready:** "rescues your crewneck sweatshirt".

When a check fails, the trace shows the failure and the repair round that fixed it. The rule picker, used in fixture mode or when the models fail, records the same kind of trace.

**Wear history from day one.** A freshly scanned closet looks freshly worn, so nothing could be rescued and the closet-alive % meant nothing. Now "when did you last wear this?" asks for a rough answer per piece: this week, this month, 1–3 months, 3–6 months, 6–12 months, or over a year. It appears in three places:
- a step in getting started
- the item sheet
- a Closet banner, shown when a third or more of your pieces have no history

These answers are estimates. They never count as wears, a logged "Wear this" always replaces them, and an older guess never hides a newer logged wear. Wearing something estimated at "3–6 months ago" triggers the 救 rescue straight away.

| Endpoint | What it does |
|---|---|
| `POST /api/wardrobe/last-worn` | `{items: [{id, days_ago}]}`: estimated last-worn dates; `days_ago: null` clears an estimate |

**Finishing touches (仕上げ).** Each look gets 2–3 small moves that make it read as styled: an underlayer that just shows, a tuck or pushed sleeves, and an accessory or two. They come from a styling playbook in `closet/styling.py`, distilled from stylist and editorial guides:
- **Layers only peek:** a hem a couple of centimetres below a knit, a collar out over a crewneck, long sleeves under a graphic tee, a turtleneck under a layer.
- **Balance volume:** pair one relaxed piece with one fitted one, using a front tuck to show the waist over wide trousers.
- **Sleeves and hems:** push sleeves to show wrists and rings; cuff jeans to show the shoes.
- **Accessories:** three at most, one main metal (silver with cool colours, gold with warm), belt leather matching the shoes, one accessory echoing a colour from a print, and shoe weight matched to trouser volume.

How it works:
1. **Muse Spark Open picks from the playbook** for the actual pieces, the weather and the plans, and writes each touch in plain words.
2. **The code checks the picks:** playbook ids only, at most one layer, one technique and two accessories, and no repeats of an earlier look's ideas.
3. **The code works out what you own** from your checklist in Notes ("Things you own but don't scan": tees, shirts, jewellery, belts, socks, shoes). Anything you haven't ticked shows as "if you have one". It's never a shopping link.
4. **The oni learns from your taps:** "I have this" ticks the basic, and "Not me" stops that touch.

Fixture mode uses a rule-based version of the same playbook.

Live (Muse Spark Open, 3–7s per look):
- "Wear a white button-up under the black crewneck so the collar peeks out."
- "Tuck front of white henley into blue wide-leg jeans."
- "Finish the charcoal track pants with chunky black boots to balance the width."

**Colour read (配色) and "Got one?" (探して).** The styling research is written up in [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md), with sources. It covers colour theory, layering, proportion and composition, texture, pattern, high/low formality, accessories and the capsule core.

- **Colour read:** each look gets one, computed from each garment's measured colour rather than its tag. Navy, denim, browns, olive and greys count as neutrals. It names the scheme (all neutral, neutral plus accent, tonal, analogous, complementary or contrasting), the light/dark contrast and the warmth.
- **A colour move:** the read decides the look's one colour play:
  - a light break for head-to-toe dark
  - one accent colour for all-neutral looks
  - echoing a print's colour
  - bookending an accent with the shoes
  - texture contrast for tonal looks

  Live on the test closet, a black sweatshirt with dark brown knit pants read "tonal, low contrast", and Spark Open suggested "Let a white tee peek just below the black sweatshirt above the dark brown pants".
- **"Got one?":** each look also asks about one core piece the closet has none of, such as a jacket on a cold day, a knit, a button-up for smart plans, or trousers. The three looks rotate through different pieces. **Scan it in** opens Scan. **I don't have one** stops that prompt and points to Thrift. It never asks you to buy anything.

| Endpoint | What it does |
|---|---|
| `GET /api/plans/{id}/touches?look=` | 2–3 finishing touches for one look, owned basics marked, plus its colour read and a "Got one?" prompt |
| `GET` / `PUT /api/style` | The basics checklist (with its catalog) and touches you skipped |

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

## Thrift (古着): gap finder and thrift list

The only shopping the oni does is second-hand, and only for pieces that earn their place. Muse Spark Open reads the wardrobe, your learned preferences, the season and recent weather. It names the 3 pieces that would unlock the most new outfits with what you already own. For each piece it gives:
- the items it goes with
- what to check on a thrift rack: the fabric content on the label, quality details and condition
- a rough second-hand price
- search terms, linked to eBay, Depop and Poshmark searches

Rules for what it suggests:
- Never a fast-fashion brand.
- No shoes or accessories: scans cover clothes, so missing shoes probably just weren't photographed.
- Nothing you've dismissed or are already watching.

**The "+N new outfits" figure is counted in code, not taken from the model.** It comes from the pairings the model lists. For example, outerwear counts every paired top × bottom it can layer over. Pieces are ranked by that count. Spark Open ignores field descriptions in the JSON schema, so the format rules are in the prompt, and a cleanup step drops invented ids, category prefixes in names, and prices that aren't ranges.

Live, on the 7-garment test closet (12s, ~1k tokens in / 3.6k out): an olive wool overshirt (+12 outfits, $35–65), tan canvas chinos (+4) and a cream cable sweater (+3). That fits: the closet has no outerwear and mornings feel like −2°.

| Endpoint | What it does |
|---|---|
| `POST /api/gaps` | The 3 pieces with their paired items expanded; `{"fresh": true}` asks again |
| `GET /api/thrift` | The thrift list: pieces being hunted, and ones found |
| `POST /api/thrift` | `{piece, status}`: watch a piece, or dismiss it so it's never suggested again |
| `PATCH` / `DELETE /api/thrift/{id}` | Mark found, or remove |
| `POST /api/thrift/example` | `{name, colors, category}`: the piece's example photo (made once, then cached) |

**Example photos.** Each gap card gets an example photo made by Muse Image (text-to-image, ~25s the first time, then cached). It shows a second-hand piece in good condition, laid flat and shot from above, the same view as your own scans, so you know the shape and colour to look for. It is labelled "EXAMPLE · AI-MADE" in the app, never presented as a real listing, and the prompt rules out logos, labels and people. Fixture mode only shows examples already made.

In the app, the Thrift tab shows gap cards with a "+N NEW OUTFITS" sticker, the pieces you own that it goes with, and the "what to look for" tips. Your list appears as WANTED 求む posters. "Found it!" stamps a poster 済 and sends you to Scan to add the piece to your closet.

## Try-on in the app

"Try it on 試着" on any Today look opens the try-on. The first time, it asks **who wears it**:
- **Mannequin** (the default): height, build, form and a finish colour, with a live preview figure. No photo of you is used.
- **My photo** (opt-in):
  - you have to tick a consent box first
  - Muse Spark checks the photo for one person, head to feet, face visible; a photo that fails is never stored
  - a photo that passes is re-encoded before saving, which strips location and camera details
  - one tap deletes it, along with every render made from it
- **Flat-lay only:** your real cutouts, no body.

**How a render is made:** it runs as a background job and the app shows progress. Muse Image renders the look, Muse Spark judges it against your real garments, and Muse Image retries once with the judge's corrections. The app shows the match score (1–5), any differences the judge found, and a one-tap "Flat-lay (exact)" view. Finished renders are cached per look and wearer, so a repeat is free and instant. Fixture mode serves cached renders, and otherwise shows the flat-lay.

**Live result:** a grey acid-wash tee with striped track pants on a 172 cm neutral mannequin took 70s and 2 tries, and scored 5/5.

That run also exposed a judge bug: it scored the render 2/5 because the mannequin's sculpted nose and lips counted as a "human face". The face rule now only triggers on a realistic face (eyes, skin, hair). Wearer notes are also shown whenever they cost points, so a low score always comes with a reason.

**Layered dress-up (the default for the mannequin).** Rendering every outfit cost about 70s and up to four model calls. Now each garment is dressed once and reused for every outfit:
1. **Base, once per body profile.** Muse Image renders a plain white mannequin, then an edit recolours it to your finish, form and build. Asking for body details on a bare mannequin trips the content filter; recolouring an existing one doesn't.
2. **Layer, once per garment.** Muse Image puts just that item on *that exact base image*. SAM 3.1 cuts the garment out, and the result is saved as a cropped transparent layer with its position on the base.
3. **Outfit, instantly.** The app stacks the layers itself: bottoms, then tops, then outerwear. Switching looks (◀ ▶) or tapping a piece to take it off needs no model call.

`spike/layers.py` showed this works: separately rendered garments differ from the base by under 1% of pixels outside the garment, so the layers line up with no alignment step.

Live on the 7-garment closet, the base plus six layers for today's three looks took about 46s with three running at once. After that, swapping looks took about 60ms.

New scans are dressed in the background, and Notes has "Dress the mannequin with my whole closet". The full render stays one tap away as **Exact render**, for tucks and drape, and the flat-lay stays one tap away too. Layers belong to one mannequin, so changing your body settings re-dresses each garment once. Photo mode keeps using full renders.

| Endpoint | What it does |
|---|---|
| `GET` / `PUT /api/tryon/profile` | Mode and mannequin details; `ready` says whether try-on can run |
| `POST` / `DELETE /api/tryon/photo` | The face version: upload (multipart `photo` + `consent=true`), checked before it's kept; delete removes its renders |
| `POST /api/tryon` | `{plan_id, look}`: starts or reuses a render job |
| `GET /api/tryon/jobs/{id}` | Poll: status, progress step, score, differences, render and flat-lay URLs |
| `POST /api/tryon/layers` | `{item_ids, prepare}`: base and per-garment layer states (with boxes), starting missing ones in live mode |
| `GET /api/tryon/flatlay` | `?plan_id&look`: the exact flat-lay, without starting a render |

## Testing on your phone

The phone and the computer must be on the same Wi-Fi.

**When friends test, give everyone their own closet.** By default there is one closet for whoever opens the app. With `--devices`, every browser gets its own:

```bash
python -m server.dev --live --devices --var var/testers    # one closet per phone, apart from your own var/
```

- **Separate folders.** Each closet's database, cutouts, renders, try-on photo and calendar live in `var/testers/closets/<id>/`. A cookie picks the closet. The model cache is shared, since it is keyed by content hashes.
- **Moving between devices.** Notes → **Your closet** has "Open on another device", a private link that opens the same closet on a second phone. "Start a new closet" begins again from empty.
- **Limits.** The var/ root is never reachable as a closet. Fixture mode never replays one closet's scans into another. `MONSTER_MAX_CLOSETS` (default 200) caps how many can be created.
- **Launch configs.** In the Claude desktop app, `api-testers` runs this live and `api-devices` runs it in fixture mode.

```bash
python -m server.dev --live                 # API in live mode: real models, every result cached
cd web && npm run dev:lan                   # front end, reachable from the phone
```

Then open `http://<your computer's Wi-Fi IP>:5173` on the phone. The first time, Windows may ask whether Node can accept connections; allow it on private networks.

The API itself only listens on localhost, and the phone reaches it through the Vite proxy. Anyone on the same Wi-Fi could open the app while this runs, so only use it on a network you trust. Live mode spends credits: scans, plans, check-ins, thrift and try-on all call real models.

In the Claude desktop app, the `api-live` and `web-lan` launch configs do the same.

## Getting started

The first time the app opens, it walks through seven short steps and saves as it goes, so leaving halfway loses nothing:

1. **Hello:** the oni introduces itself, with three promises: only what you own, dressed for your day, and second-hand first.
2. **Where are you?** City search using Open-Meteo geocoding (free, no key), or "Use my location" where the browser allows it. There's an optional "I run cold / warm" choice, which seeds a preference the planner reads from day one.
3. **What's on?** Upload an `.ics` export from Google or Apple Calendar, use the demo calendar, or skip. Only event titles, times and places are read, and the file stays in `var/private/`.
4. **Feed me clothes:** a flat-lay guide (4–8 pieces, no overlaps, print side up), then scanning in batches. **Next** unlocks once there's at least a top and a bottom, or a dress.
   - A short note says where the photos go.
   - **No clothes handy? Try a sample closet** loads 9 made-up pieces instead, some unworn for months, so there is something to rescue straight away.
5. **When did you last wear these?** A rough answer per piece, so forgotten clothes are visible from day one.
6. **Who wears it?** The try-on setup, which can be skipped. Choosing the mannequin starts dressing your whole closet in the background.
7. **Your first pick:** a real plan for today, with your weather and calendar. "See my day" finishes setup.

Notes → **Your setup** reopens the flow from step 2, to change your city or calendar. The planner, thrift finder and check-ins now use the saved location and calendar; `.env` values are only the fallback before setup.

| Endpoint | What it does |
|---|---|
| `GET` / `PUT /api/profile` | Location, calendar choice, onboarded flag; also closet counts and whether a plan is possible |
| `POST` / `DELETE /api/profile/calendar` | Upload an `.ics` (checked for events, max 2 MB), or remove it |
| `GET /api/geocode?q=` | City search for the weather location |
| `POST /api/preferences` | A preference the user states directly, stored like learned ones |
| `GET /api/closet` | Which closet this browser is on (`per_device`, `id`) |
| `POST /api/closet/open` · `/new` · `/sample` | Open a closet from its link, start a fresh one, or load the sample closet |

**The sample closet** is `fixtures/sample_closet/`. None of it is anyone's real clothes:
- `scripts/make_sample_closet.py` has Muse Image draw two flat-lay photos.
- The app's own scan path (SAM 3.1 cutouts, then Muse Spark tags) turns them into 9 items, for about 5 cents.
- Each piece ships with an estimated last-worn date.

**Small closets.**
- A closet that can't make an outfit yet gets a message naming what to scan next, for example "I need at least one bottom", instead of failing.
- One top and one bottom make one look, not three copies of it.
- A closet of only dresses works too.

## Front end (mobile web)

React + Vite in `web/`, styled after the Tokyo-street wireframes (washi, sumi, shu for the oni, ai for your day). Run the API and the dev server side by side; Vite proxies `/api` to port 8000:

```bash
uvicorn server.main:app --reload        # terminal 1 (add MONSTER_MODE=live for real model calls)
cd web && npm install && npm run dev    # terminal 2 → http://localhost:5173
```

Screens:
- **Today:** the oni's looks as a cutout collage on riso halftone, with weather and calendar on a ticker.
  - By default it shows one look with **Wear this** and **Next look**.
  - Finishing touches, the colour read, "Got one?", the adjust chips (Warmer, Dressier, No black, Re-roll) and "How the oni decided" sit under **More**.
  - Notes → **Today view → Everything** keeps all of that open and names the models at work. Opening the app with `?view=full` does the same; this is the view for judges and demos.
  - The closet-alive % stays hidden until there is some wear history behind it.
  - **Plans are made ahead.** After a wear or an evening check-in, tomorrow's plan is built in the background, so the morning opens on it instead of waiting about 15s. If the closet changes after that plan was made, it is dropped and a fresh one is made.
- **Worn it!:** confetti, the fed oni, the 救 stamp for rescued pieces, closet-alive change and streak.
- **Evening check-in:** temperature, feeling, tags and a note; shows the oni's reply and what it learned.
- **Closet:** a searchable, filterable pinboard grid, with an item sheet showing tags and a remove action.
- **Scan:** pick 1–10 flat-lay photos and build the closet.
- **Thrift:** the gap finder and the thrift list (see above).
- **Notes:** the oni's mood, closet-alive meter and every learned preference. Each preference can be forgotten.

**Dark mode.** The app follows the system theme, or you can force Light or Dark under Notes → Appearance (remembered on the device). Dark inverts the print: ink-dark ground, light ink, the same hard shadows. Two things stay put on purpose: photo slots stay a mid-tone paper so black and white garments both stay visible, and the evening check-in keeps its night palette.

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
- **Testers' closets are kept apart.** With `--devices`, each phone's photos, cutouts and renders stay in its own closet folder, and the app says so before the first scan.
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
