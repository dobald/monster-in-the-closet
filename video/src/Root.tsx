import { Composition, Folder } from "remotion";
import { SceneText } from "./components/SceneText";
import { Stamp } from "./components/Stamp";
import { Backdrop } from "./components/Backdrop";
import { Demo } from "./Demo";
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

// Demo length: 3339 frames (1:51.3), cut to the beat of "Local Forecast": see Demo.tsx.
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Demo"
        component={Demo}
        durationInFrames={3339}
        fps={30}
        width={1920}
        height={1080}
      />
      <Folder name="Scenes">
        <Composition
          id="Hook"
          component={Hook}
          durationInFrames={179}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Stakes"
          component={Stakes}
          durationInFrames={154}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Quote"
          component={Quote}
          durationInFrames={179}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Scan"
          component={Scan}
          durationInFrames={308}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Findings"
          component={Findings}
          durationInFrames={212}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Shape"
          component={Shape}
          durationInFrames={250}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Dedupe"
          component={Dedupe}
          durationInFrames={275}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Learn"
          component={Learn}
          durationInFrames={190}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Today"
          component={Today}
          durationInFrames={308}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Agent"
          component={Agent}
          durationInFrames={192}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Scores"
          component={Scores}
          durationInFrames={251}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Rescued"
          component={Rescued}
          durationInFrames={247}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Evening"
          component={Evening}
          durationInFrames={231}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Renders"
          component={Renders}
          durationInFrames={211}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Models"
          component={Models}
          durationInFrames={248}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Outro"
          component={Outro}
          durationInFrames={174}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
      </Folder>
      <Folder name="Elements">
        <Composition
          id="Backdrop"
          component={Backdrop}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kanji: "服",
            style: { backgroundColor: "#1e1b19", color: "#ede6da" },
          }}
        />
        <Composition
          id="Stamp"
          component={Stamp}
          durationInFrames={60}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            text: "選",
            color: "#c4472f",
            size: 300,
            at: 0.3,
            style: { left: 810, top: 390 },
          }}
        />
        <Composition
          id="SceneText"
          component={SceneText}
          durationInFrames={90}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kicker: "01 · FEED ME · 服をちょうだい",
            title: "LAY CLOTHES FLAT. SNAP ONE PHOTO.",
            body: "SAM 3.1 cuts out every piece with one “clothing” prompt.",
            accent: "#c4472f",
            delay: 0,
            style: { position: "absolute", left: 120, top: 200, width: 700 },
          }}
        />
      </Folder>
    </>
  );
};
