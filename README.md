# Monster in the Closet

> It noticed I haven't worn 60% of my closet and dressed me in it for today, without me asking.

A closet-first morning agent:
1. Film a 15-second video of your closet.
2. **SAM 3.1** finds and tracks every garment, and **Muse Spark** catalogs each one.
3. Each morning, the agent picks an outfit from clothes you already own. It takes the weather and your calendar into account and favours pieces you've forgotten about.

Built for the **Meta Global AI Developer Hackathon** (Indie track, *Build for Your World*).

## Built during the hackathon

Everything in this repository was written during the hackathon (Oct 26 – Nov 4, 2026), starting from an empty folder. The commit history is the record.

## Meta models used

| Model | Role |
|---|---|
| SAM 3.1 | Segments and tracks garments across a closet video. A stable object id per garment means no double-counting. |
| Muse Spark 1.3 | Tags each item with structured output, plans outfits, and checks render fidelity. |
| Muse Image | Optional try-on render of you in your own clothes. |
| Muse Voice Transcribe | Voice tweaks: "nothing black, dinner outside" *(planned)* |
| Muse Spark Open (via Baseten) | Open-weights tagging path *(planned)* |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # then add MODEL_API_KEY
```

## Day-0 spike

This is a go/no-go test on real footage. Put your media in `data/`, which git ignores:

```bash
python spike/spike.py all data/closet.mp4 --person data/me.jpg --expected 25 --dry-run   # cost estimate
python spike/spike.py all data/closet.mp4 --person data/me.jpg --expected 25
```

Each run writes to `out/<timestamp>/`:
- `SUMMARY.md`: pass/fail on segmentation, double-counting and render fidelity
- `contact_sheet.png` and `cutouts/`: every garment SAM found
- `wardrobe.json`: Muse Spark's tags
- `render.png` and `flatlay.png`: the try-on next to the always-faithful flat-lay

You can also run the steps on their own: `segment`, `tag`, `render`. Run `python spike/spike.py -h` for details.

Offline self-test (no API calls): `python tests/test_offline.py`

## Privacy

Closet footage, selfies and renders stay in `data/` and `out/`. Both folders are git-ignored and never committed. This repo is public.

## Layout

```
closet/       shared code: config + provider routing, schema, SAM client, media, models
spike/        Day-0 go/no-go script
tests/        offline tests
data/ out/    local only (ignored)
```
