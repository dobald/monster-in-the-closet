import type React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

// A finger tap on a phone screen: a dot presses in and a ring spreads out. Place it as a
// child of <Phone>, in screen points (the phone screen is 430 × 932).
export const Tap: React.FC<{
  readonly x: number;
  readonly y: number;
  readonly at: number;
}> = ({ x, y, at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [at * fps, (at + 0.6) * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (p <= 0 || p >= 1) return null;
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: x - 22,
          top: y - 22,
          width: 44,
          height: 44,
          borderRadius: 22,
          background: "rgba(43, 39, 36, 0.35)",
          scale: String(p < 0.2 ? 0.7 + p * 1.5 : 1),
          opacity: 1 - p,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: x - 22,
          top: y - 22,
          width: 44,
          height: 44,
          borderRadius: 22,
          border: "4px solid #c4472f",
          scale: String(1 + p * 1.8),
          opacity: 1 - p,
        }}
      />
    </>
  );
};
