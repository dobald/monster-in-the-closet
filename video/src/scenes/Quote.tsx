import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop } from "../components/Backdrop";
import { Camera } from "../components/Camera";
import { display, mono } from "../theme";

const WORDS =
  "“IT NOTICED I HAVEN'T WORN 60% OF MY CLOSET AND DRESSED ME IN IT FOR TODAY, WITHOUT ME ASKING.”".split(
    " ",
  );

const QuoteInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Words light up one after another, like they're being read aloud.
  const at = (i: number) => (0.3 + i * 0.16 + (i > 5 ? 0.3 : 0)) * fps;
  return (
    <>
      <Backdrop name="Backdrop" kanji="目標" />
      <Camera hits={[0.3 + 5 * 0.16 + 0.05]}>
        <Interactive.Div
          name="Quote label"
          style={{
            position: "absolute",
            left: 160,
            top: 170,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.12em",
            color: "#e9b43c",
            opacity: interpolate(frame, [0, 0.4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          THE GOAL · 目標
        </Interactive.Div>
        <Interactive.Div
          name="Quote"
          style={{
            position: "absolute",
            left: 160,
            top: 250,
            width: 1600,
            fontFamily: display,
            fontSize: 96,
            lineHeight: 1.05,
            color: "#f3eee5",
          }}
        >
          {WORDS.map((w, i) => {
            const hero = w === "60%";
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  marginRight: "0.24em",
                  color: hero ? "#c4472f" : "#f3eee5",
                  opacity: interpolate(
                    frame,
                    [at(i), at(i) + 0.15 * fps],
                    [0.12, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                  ),
                  scale: String(
                    interpolate(
                      frame,
                      [at(i), at(i) + 0.3 * fps],
                      [hero ? 2.2 : 1.15, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.bezier(0.16, 1, 0.3, 1),
                      },
                    ),
                  ),
                }}
              >
                {w}
              </span>
            );
          })}
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Quote = Interactive.create({
  Component: QuoteInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
