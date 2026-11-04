import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop } from "../components/Backdrop";
import { Camera } from "../components/Camera";
import { Phone } from "../components/Phone";
import { SceneText } from "../components/SceneText";
import { Tap } from "../components/Tap";
import { mono } from "../theme";

// Four onboarding screens deal in like cards, each with a one-word label.
const LearnInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const deal = (at: number, rot: number) => ({
    opacity: interpolate(frame, [at * fps, (at + 0.15) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    translate: `0px ${interpolate(
      frame,
      [at * fps, (at + 0.6) * fps],
      [700, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.bezier(0.16, 1, 0.3, 1),
      },
    )}px`,
    rotate: `${interpolate(
      frame,
      [at * fps, (at + 0.6) * fps],
      [rot * 6, rot],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.bezier(0.16, 1, 0.3, 1),
      },
    )}deg`,
  });
  const label = (at: number) => ({
    scale: String(
      interpolate(frame, [(at + 0.5) * fps, (at + 0.8) * fps], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.bezier(0.34, 1.56, 0.64, 1),
      }),
    ),
  });
  return (
    <>
      <Backdrop name="Backdrop" kanji="好み" />
      <Camera hits={[]}>
        <SceneText
          name="Learn caption"
          kicker="02 · GETTING TO KNOW YOU · はじめまして"
          title="ONE MINUTE OF SETUP."
          body=""
          accent="#6a8db2"
          delay={0}
          style={{ position: "absolute", left: 120, top: 50, width: 1680 }}
        />

        <Interactive.Div
          name="Weather phone"
          style={{
            position: "absolute",
            left: 150,
            top: 300,
            ...deal(0.6, -3),
          }}
        >
          <Phone src="02-weather" scale={0.6}>
            <Tap x={215} y={357} at={1.8} />
          </Phone>
          <div
            style={{
              ...label(0.6),
              marginTop: 30,
              display: "inline-block",
              fontFamily: mono,
              fontSize: 30,
              letterSpacing: "0.1em",
              background: "#34506b",
              color: "#f3eee5",
              padding: "10px 18px",
              borderRadius: 8,
            }}
          >
            WEATHER
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Calendar phone"
          style={{ position: "absolute", left: 575, top: 300, ...deal(1.4, 2) }}
        >
          <Phone src="03-day" scale={0.6} />
          <div
            style={{
              ...label(1.4),
              marginTop: 30,
              display: "inline-block",
              fontFamily: mono,
              fontSize: 30,
              letterSpacing: "0.1em",
              background: "#34506b",
              color: "#f3eee5",
              padding: "10px 18px",
              borderRadius: 8,
            }}
          >
            CALENDAR
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Last worn phone"
          style={{
            position: "absolute",
            left: 1000,
            top: 300,
            ...deal(2.2, -1.5),
          }}
        >
          <Phone src="06-history" scale={0.6} />
          <div
            style={{
              ...label(2.2),
              marginTop: 30,
              display: "inline-block",
              fontFamily: mono,
              fontSize: 30,
              letterSpacing: "0.1em",
              background: "#c4472f",
              color: "#ffffff",
              padding: "10px 18px",
              borderRadius: 8,
            }}
          >
            LAST WORN
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Taste phone"
          style={{
            position: "absolute",
            left: 1425,
            top: 300,
            ...deal(3, 2.5),
          }}
        >
          <Phone src="07-taste" scale={0.6}>
            <Tap x={113} y={424} at={4.4} />
          </Phone>
          <div
            style={{
              ...label(3),
              marginTop: 30,
              display: "inline-block",
              fontFamily: mono,
              fontSize: 30,
              letterSpacing: "0.1em",
              background: "#e9b43c",
              color: "#2b2724",
              padding: "10px 18px",
              borderRadius: 8,
            }}
          >
            TASTE
          </div>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Learn = Interactive.create({
  Component: LearnInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
