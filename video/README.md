# Demo video

A 1:53 Remotion video for the hackathon submission: 1920×1080, 30 fps, scored to "Local Forecast" by Kevin MacLeod. Its motion rules (palette, one easing per job, stagger frames, transitions, the oni's acting, the avoid list) are in [STYLE.md](STYLE.md); check new scenes against it.

On-screen text is kept to headlines, short labels and numbers, so a voiceover can carry the detail.

The video itself uses the app's dark theme (ground `#1e1b19`, ink `#ede6da`, cards `#2c2825`, light hard shadows, a calm riso-print backdrop), while the app captures stay in the light theme for contrast. Garments shown outside a phone sit on a light photo slot or get a thin light outline, so black and navy pieces don't disappear.

Five "Under the hood" scenes (Findings, Shape, Dedupe, Scores, Renders) are drawn from real data, not mock-ups: the README's measured results, the app's own score() trace, and the sample tee's convex hull measured the way `closet/scan.py` does it (`src/data/tee-hull.json`).

```bash
npm i
npm run dev        # Remotion Studio (or the "video" launch config, on :3000)
```

- `src/Demo.tsx` is the full timeline: fifteen scenes joined by eight 18-frame irises (`IrisTransition`), two 24-frame noren curtains and four 15-frame wipes or slides. If you change a scene's or a transition's length, change `durationInFrames` of the `Demo` composition in `src/Root.tsx` to match.
- Each scene in `src/scenes/` is also registered on its own under **Scenes**, so you can open and edit it on its own timeline.
- `src/Oni.tsx` is the app's oni (`web/src/Oni.tsx`) with its CSS motion swapped for frame-driven motion, plus blinks, `look` (where its eyes point), squash and stretch, `wave` and `chomp`.
- Shared motion pieces in `src/components/`:
  - `Backdrop`: the depth behind every scene: a pool of light, halftone dots at the edges, one ghost kanji per scene and paper grain. Also under **Elements**.
  - `Camera`: a slow push-in over a scene, plus a short shake at each time in `hits`.
  - `Stamp`: a hanko that thumps down at `at` seconds. Also under **Elements**.
  - `SceneText`: a kicker that types itself, then a word-by-word headline.
  - `Phone`: tilts in, floats, and swipes between `screens`. `zoom` with `focus`, `travel` and `spotlight` brings the whole phone toward the camera around one detail. `Tap` draws a finger tap on it.
  - `NorenTransition`: the curtain transition.

## Music

"Local Forecast" by Kevin MacLeod, in `public/audio/local-forecast.mp3` (from incompetech.com). It is free under Creative Commons Attribution 4.0, which requires this credit. It is on the end card; put it in the video description too:

```
"Local Forecast"
Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0
http://creativecommons.org/licenses/by/4.0/
```

The edit is cut to its beat: 92.99 bpm with the first beat at 0.313 s (measured from the audio), so one beat is 19.36 frames. Every transition starts on a beat, and the oni's landing, "STARVES", the bite and the "fed" moment land on beats too. The music plays at 80 % and fades out over the last 3 s. Once the voiceover is in, lower the music under it with the `volume` curve on the `Music: Local Forecast` audio in `src/Demo.tsx`.

## Rendering

Only when you want the file:

```bash
npx remotion render Demo out/demo.mp4
```

`out/` is git-ignored, as is every `*.mp4` in the repo.

## Re-capturing app screens

The phone screens in `public/captures/` come from the app in demo mode with the sample closet. To redo them, start the `api-scratch` and `web` launch configs (a throwaway closet, no paid calls), then:

```bash
node scripts/capture.mjs              # onboarding, tabs, agent, in that order
node scripts/capture.mjs tabs agent   # or just some steps
```

Onboarding progress is saved in the closet, so for a clean first run delete `var/scratch` first. The `agent` step presses "Wear this", which marks that look worn.
