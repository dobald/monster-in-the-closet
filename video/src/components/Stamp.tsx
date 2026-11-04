import type React from "react";
import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { display } from "../theme";

// A hanko stamp, like the app's 選 seal: it drops from above the page, thumps down with an
// overshoot, and leaves an ink ring that spreads and fades. Pair `at` with a Camera hit.
const StampInner = ({
  text,
  color,
  size,
  at,
  style,
}: {
  readonly text: string;
  readonly color: string;
  readonly size: number;
  readonly at: number;
  readonly style?: React.CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = at * fps;
  const land = start + 0.22 * fps;
  return (
    <div style={{ position: "absolute", width: size, height: size, ...style }}>
      <div
        style={{
          position: "absolute",
          inset: -size * 0.1,
          borderRadius: "50%",
          border: `${size * 0.04}px solid ${color}`,
          opacity:
            interpolate(frame, [land, land + 0.5 * fps], [0.8, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }) * (frame >= land ? 1 : 0),
          scale: String(
            interpolate(frame, [land, land + 0.5 * fps], [0.9, 1.7], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          ),
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          border: `${size * 0.06}px solid ${color}`,
          background: "#2c2825",
          color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: display,
          fontSize: size * 0.5,
          rotate: `${interpolate(frame, [start, land], [-28, 12], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}deg`,
          opacity: interpolate(frame, [start, start + 0.08 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          scale: String(
            interpolate(frame, [start, land, land + 0.18 * fps], [3, 0.92, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.out(Easing.quad),
            }),
          ),
        }}
      >
        {text}
      </div>
    </div>
  );
};

export const Stamp = Interactive.create({
  Component: StampInner,
  layout: "none",
  schema: {
    text: { type: "string", default: "選", description: "Kanji" },
    color: { type: "color", default: "#c4472f", description: "Ink" },
    size: {
      type: "number",
      default: 140,
      min: 40,
      step: 1,
      description: "Size",
      hiddenFromList: false,
    },
    at: {
      type: "number",
      default: 1,
      min: 0,
      step: 0.1,
      description: "Lands at (s)",
      hiddenFromList: false,
    },
  },
});
