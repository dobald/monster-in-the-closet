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
  - The face version needs a clear photo, or Muse Image invents a face.
  - Body-detail wording can trip Muse Image's content filter, so the prompt falls back to simpler wording.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # then add MODEL_API_KEY
```

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
  - **Closet video → Meta, for SAM segmentation.** It's deleted from Meta's file storage as soon as segmentation finishes.
  - **Garment cutouts → Baseten (Muse Spark Open), for tagging.**
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
closet/       shared code: config + provider routing, schema, SAM client, media, models
spike/        Day-0 go/no-go script
tests/        offline tests
data/ out/    local only (ignored)
```
