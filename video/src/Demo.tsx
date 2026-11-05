import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Audio, Video } from "@remotion/media";
import { interpolate, Sequence, staticFile } from "remotion";
import { iris } from "./components/IrisTransition";
import { noren } from "./components/NorenTransition";
import { Agent } from "./scenes/Agent";
import { Dedupe } from "./scenes/Dedupe";
import { Evening } from "./scenes/Evening";
import { Findings } from "./scenes/Findings";
import { Hook } from "./scenes/Hook";
import { Learn } from "./scenes/Learn";
import { Models } from "./scenes/Models";
import { Outro } from "./scenes/Outro";
import { Quote } from "./scenes/Quote";
import { Renders } from "./scenes/Renders";
import { Rescued } from "./scenes/Rescued";
import { Scan } from "./scenes/Scan";
import { Scores } from "./scenes/Scores";
import { Shape } from "./scenes/Shape";
import { Stakes } from "./scenes/Stakes";
import { Today } from "./scenes/Today";

// Your intro clip (public/intro/intro.mp4, made from "Video Intro.mov": 1080p, SDR, voice levelled to -13 LUFS).
// Its picture ends at 8.54 s and the clip itself is black while you say "damn, I'm getting there".
// The demo cuts in on the "M" of "Monster in the closet" (10.25 s in the clip); the clip keeps
// playing underneath so the rest of the line ("start with what you own...") runs over the Hook.
export const INTRO = 307; // frames of clip before the demo cuts in
const CLIP = 430; // the clip's full length, 14.35 s
const MAIN = 3339; // the demo itself
export const DEMO_FRAMES = INTRO + MAIN;

// Music: "Local Forecast" (Kevin MacLeod, 92.99 bpm, first beat at 0.313 s, measured from the
// audio) now starts on frame 0, under the intro. It starts 3 frames into the track so that the demo
// cuts in exactly 16 beats later (16 beats = 10.32 s = 310 frames, minus the 307-frame intro), which
// keeps every cut below on the same beat grid as before. Scene lengths are frame counts chosen so
// every transition starts on a beat (one beat = 19.36 frames). If you change one, keep its cut on
// the grid and change MAIN by the same amount. If you change INTRO, change MUSIC_TRIM by the
// opposite amount so INTRO + MUSIC_TRIM stays 310.
const MUSIC_TRIM = 3;
// Under your voice the music sits at 10 % (about 16 dB below the voice), then rises to 80 % once
// you stop talking. Lower DUCKED if you want the voice even clearer.
const DUCKED = 0.1;
const FULL = 0.8;
const VOICE_ENDS = 423; // 14.1 s, just after "...fast fashion"
const RISE = 21; // frames the music takes to come back up

export const Demo = () => {
  return (
    <>
      <Sequence name="Intro: your clip" durationInFrames={CLIP}>
        <Video src={staticFile("intro/intro.mp4")} />
      </Sequence>
      <Sequence name="Demo" from={INTRO} durationInFrames={MAIN}>
        <TransitionSeries name="Scenes">
          <TransitionSeries.Sequence name="Hook" durationInFrames={179}>
            <Hook style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={wipe({ direction: "from-left" })}
            timing={linearTiming({ durationInFrames: 15 })}
          />
          <TransitionSeries.Sequence name="Stakes" durationInFrames={154}>
            <Stakes style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 27, y: 52, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Quote" durationInFrames={179}>
            <Quote style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={noren()}
            timing={linearTiming({ durationInFrames: 24 })}
          />
          <TransitionSeries.Sequence name="Scan" durationInFrames={308}>
            <Scan style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 83, y: 50, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Findings" durationInFrames={212}>
            <Findings style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 92, y: 41, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Shape" durationInFrames={250}>
            <Shape style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 22, y: 55, color: "#34506b" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Dedupe" durationInFrames={275}>
            <Dedupe style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={noren()}
            timing={linearTiming({ durationInFrames: 24 })}
          />
          <TransitionSeries.Sequence name="Learn" durationInFrames={190}>
            <Learn style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={slide({ direction: "from-right" })}
            timing={linearTiming({ durationInFrames: 15 })}
          />
          <TransitionSeries.Sequence name="Today" durationInFrames={308}>
            <Today style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 83, y: 50, color: "#34506b" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Agent" durationInFrames={192}>
            <Agent style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 36, y: 78, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Scores" durationInFrames={251}>
            <Scores style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 93, y: 32, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Rescued" durationInFrames={247}>
            <Rescued style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={slide({ direction: "from-bottom" })}
            timing={linearTiming({ durationInFrames: 15 })}
          />
          <TransitionSeries.Sequence name="Evening" durationInFrames={231}>
            <Evening style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 86, y: 57, color: "#c4472f" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Renders" durationInFrames={211}>
            <Renders style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={iris({ x: 83, y: 81, color: "#34506b" })}
            timing={linearTiming({ durationInFrames: 18 })}
          />
          <TransitionSeries.Sequence name="Models" durationInFrames={248}>
            <Models style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition
            presentation={wipe({ direction: "from-left" })}
            timing={linearTiming({ durationInFrames: 15 })}
          />
          <TransitionSeries.Sequence name="Outro" durationInFrames={174}>
            <Outro style={{ backgroundColor: "#1e1b19", color: "#ede6da" }} />
          </TransitionSeries.Sequence>
        </TransitionSeries>
      </Sequence>
      {/* Music: a 6-frame fade in to avoid a click, ducked under your voice, then a 3 s fade out
          ending on the last frame. */}
      <Audio
        name="Music: Local Forecast"
        src={staticFile("audio/local-forecast.mp3")}
        trimBefore={MUSIC_TRIM}
        durationInFrames={DEMO_FRAMES}
        volume={(f) =>
          interpolate(
            f,
            [0, 6, VOICE_ENDS, VOICE_ENDS + RISE, DEMO_FRAMES - 90, DEMO_FRAMES],
            [0, DUCKED, DUCKED, FULL, FULL, 0],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          )
        }
      />
    </>
  );
};
