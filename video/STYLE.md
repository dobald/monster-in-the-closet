# Video style

The rules the demo video follows, written as numbers so any new scene can be checked against them. 1920×1080, 30 fps.

## Palette

The video uses the app's dark theme; the app's own screens stay light, for contrast.

| Role | Hex |
|---|---|
| Ground | `#1e1b19` |
| Card | `#2c2825` |
| Ink (text, outlines, hard shadows) | `#ede6da` |
| Muted text | `#a39a8e`, secondary `#cfc7ba` |
| Accent: shu red | `#c4472f` (fills), `#d9573d` (text on dark) |
| Ai indigo | `#34506b` (fills), `#6a8db2` (text on dark) |
| Tiger yellow | `#e9b43c`, always with dark ink `#2b2724` on top |
| Photo slot behind garments | `#a79e91` or `#e6dfd2` |

- **One accent per shot.** Red marks the subject: the hero word, the winning card, the lit model, the key number. Kickers stay muted; the accent only marks the headline's underline.
- Black and navy garments never sit straight on the ground: they go on a light photo slot or get a thin `#ede6da` outline.

## Easing: one curve per job

| Job | Curve | Length |
|---|---|---|
| Enter and settle: headlines, cards, phones, lists, zooms | `cubic-bezier(0.16, 1, 0.3, 1)` | 20–30 frames |
| Snap: screen swipes, iris cuts | `cubic-bezier(0.7, 0, 0.2, 1)` | 15–18 frames |
| Data: bars growing from a baseline | ease-out cubic | 20 frames |
| Pop: stickers, stamps, the oni, one key hit per scene | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 9–12 frames |

No other curves. Overshoot is only for pop.

## Timing

- Headline words rise out of their own mask, **3 frames apart, 21 frames each**. Never fade text in.
- Something lands in the first second of the video (the oni drops at 0.15 s, lands at 0.55 s).
- Beats follow each other closely: a scene ends about 1.5–2 s after its last beat lands. Leave longer holds only where a voiceover needs them.
- Any text on screen gets about 0.3 s per word to read, and at least 1 s.
- A screen action (tap, swipe) every 3–4 s, with about 8 frames between the tap and what it causes.
- For the detail that matters, the **whole phone comes toward the camera**: it grows to 1.5× around that detail, travels it toward the middle of the frame, turns about 5° to face you and lifts on a deeper shadow, then settles back once the action is done (0.8 s in, 0.7 s out, enter curve). Where nothing else needs reading, the rest of the scene dims to 50 % while it is close.
- Camera: a slow push-in of 3.5 % across each scene, plus a short shake (0.4 s, decaying) only on impacts: stamps, the bite, the landing.

## Depth: the backdrop

Depth comes from print, not light effects, and nothing in the background flashes or moves faster than a few pixels a second.

- A soft pool of light behind the content (`#2a2522` to `#1e1b19`), falling off to `#141210` at the edges.
- Two halftone dot fields: a far indigo one (22 px cells, 2.2 px dots) and a near red one (34 px cells, 4 px dots), drifting 3–6 px/s in different directions, masked to the edges so the middle stays clean.
- One ghost kanji per scene, 640 px, outlined only (ink at 7 %), with an indigo plate 10 px off register; it drifts up 6 px/s.
- A still paper grain at 6 % over everything.

## Transitions

Motion carries across the cut; no fades.

- **Iris** (18 frames): the next scene opens in a circle out of the outgoing shot's subject, led by an ink ring.
- **Noren** (24 frames): curtain panels drop, the scene swaps behind them, panels lift.
- **Wipe or slide** (15 frames) for the remaining cuts.

## The oni

- Its own motion runs **on twos**: it changes every 2 frames, like hand-drawn animation. The camera and UI stay at 30 fps.
- **Line boil**: 3 seeded wobble variants of its outline, cycling every 2 frames.
- **Anticipation** before big actions: a lean back of 4–6 frames before the bite.
- **Smear** on fast moves instead of motion blur: it stretches tall as it falls, then squashes on landing.
- The off-register indigo layer behind it stays 5 px right and 4 px down.

## Type

- Display: Dela Gothic One. Body: Zen Kaku Gothic New. Labels: JetBrains Mono.
- Nothing smaller than **28 px** (26 px only inside the dense tag card).
- Keep key text 120 px from the sides and about 80 px from the top and bottom.

## Avoid

Glow and neon blur, particle bursts (the rescue's confetti is the one exception), lens flares, RGB split, glitch, decorative gradients, overshoot on everything, fades, and text that repeats what the picture already shows.
