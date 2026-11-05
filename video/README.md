# Demo video

A 1:51 Remotion video for the hackathon submission: 1920×1080, 30 fps, scored to "Local Forecast" by Kevin MacLeod. Its motion rules (palette, one easing per job, stagger frames, transitions, the oni's acting, the avoid list) are in [STYLE.md](STYLE.md); check new scenes against it.

On-screen text is kept to headlines, short labels and numbers, so a voiceover can carry the detail.

The video itself uses the app's dark theme (ground `#1e1b19`, ink `#ede6da`, cards `#2c2825`, light hard shadows, a calm riso-print backdrop), while the app captures stay in the light theme for contrast. Garments shown outside a phone sit on a light photo slot or get a thin light outline, so black and navy pieces don't disappear.

The Stakes scene's two figures are from the Ellen MacArthur Foundation's *A New Textiles Economy* (2017), credited on screen: clothing utilisation fell 36% in 15 years, and the equivalent of one garbage truck of textiles is landfilled or burned every second. Five "Under the hood" scenes (Findings, Shape, Dedupe, Scores, Renders) are drawn from real data, not mock-ups: the README's measured results, the app's own score() trace, and the sample tee's convex hull measured the way `closet/scan.py` does it (`src/data/tee-hull.json`).

```bash
npm i
npm run dev        # Remotion Studio (or the "video" launch config, on :3000)
```

- `src/Demo.tsx` is the full timeline: sixteen scenes joined by nine 18-frame irises (`IrisTransition`), two 24-frame noren curtains and four 15-frame wipes or slides. If you change a scene's or a transition's length, change `durationInFrames` of the `Demo` composition in `src/Root.tsx` to match.
- Each scene in `src/scenes/` is also registered on its own under **Scenes**, so you can open and edit it on its own timeline.
- `src/Oni.tsx` is the app's oni (`web/src/Oni.tsx`) with its CSS motion swapped for frame-driven motion, plus blinks, `look` (where its eyes point), squash and stretch, `wave` and `chomp`.
- Shared motion pieces in `src/components/`:
  - `Backdrop`: the depth behind every scene: a pool of light, halftone dots at the edges, one ghost kanji per scene and paper grain. Also under **Elements**.
  - `Camera`: a slow push-in over a scene, plus a short shake at each time in `hits`.
  - `Stamp`: a hanko that thumps down at `at` seconds. Also under **Elements**.
  - `SceneText`: a kicker that types itself, then a word-by-word headline.
  - `Phone`: tilts in, floats, and swipes between `screens`. `zoom` with `focus`, `travel` and `spotlight` brings the whole phone toward the camera around one detail. `Tap` draws a finger tap on it.
  - `NorenTransition`: the curtain transition.

## Intro clip

The video opens with your clip, `public/intro/intro.mp4`. It plays until you say "Monster in the closet", and the demo cuts in on that line. Your voice keeps going under the first scene. The clip's own black section covers "damn, I'm getting there".

`intro.mp4` is made from `Video Intro.mov`, which is a 4K HDR HEVC file. Chrome can't reliably decode that format, so the copy is 1080p, tone-mapped to SDR H.264, with the voice levelled to -13 LUFS. Neither file is committed, because the repo ignores `*.mov` and `*.mp4`. To remake the copy after re-exporting the clip:

```bash
npx remotion ffmpeg -i "Video Intro.mov" -vf "zscale=t=linear:npl=203:tin=arib-std-b67:min=bt2020nc:pin=bt2020,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,scale=1920:1080:flags=lanczos" -af "loudnorm=I=-13:TP=-1:LRA=7" -ar 48000 -c:v libx264 -crf 17 -c:a aac -b:a 192k -movflags +faststart public/intro/intro.mp4
```

If the timing of your lines changes, update `INTRO` (the frame the demo cuts in on), `CLIP` (the clip's full length) and `MUSIC_TRIM` in `src/Demo.tsx`. The comment there explains how to keep the music on the beat.

## Music

"Local Forecast" by Kevin MacLeod, in `public/audio/local-forecast.mp3` (from incompetech.com). It is free under Creative Commons Attribution 4.0, which requires this credit. It is on the end card; put it in the video description too:

```
"Local Forecast"
Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0
http://creativecommons.org/licenses/by/4.0/
```

The edit is cut to its beat: 92.99 bpm with the first beat at 0.313 s (measured from the audio), so one beat is 19.36 frames. Every transition starts on a beat, and the oni's landing, "STARVES", the bite and the "fed" moment land on beats too. The music starts on the first frame of the intro, 3 frames into the track, so the demo cuts in exactly 16 beats later and stays on the grid. It sits at 10 % under your intro voice, rises to 80 % once you stop talking, and fades out over the last 3 s. For more voiceover later, add another low stretch to the `volume` curve on the `Music: Local Forecast` audio in `src/Demo.tsx` (`DUCKED` is the level used under your voice).

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
