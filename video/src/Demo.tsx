import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Audio } from "@remotion/media";
import { interpolate, staticFile } from "remotion";
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

// The hackathon demo, cut to "Local Forecast" (Kevin MacLeod, 92.99 bpm, first beat at 0.313 s,
// measured from the audio). Scene lengths are frame counts chosen so every transition starts on a
// beat (one beat = 19.36 frames). If you change one, keep its cut on the grid, and change the Demo
// composition's durationInFrames in Root.tsx by the same amount.
export const Demo = () => {
  return (
    <>
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
      {/* Music: a 6-frame fade in to avoid a click, then fades out over the last 3 s, ending on the last frame. */}
      <Audio
        name="Music: Local Forecast"
        src={staticFile("audio/local-forecast.mp3")}
        durationInFrames={3339}
        volume={(f) =>
          interpolate(f, [0, 6, 3249, 3339], [0, 0.8, 0.8, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        }
      />
    </>
  );
};
