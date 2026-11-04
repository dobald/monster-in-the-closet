import type React from "react";
import { useId } from "react";
import { Interactive, useCurrentFrame, useVideoConfig } from "remotion";
import { display } from "../theme";

// Depth behind every scene, printed rather than lit, so it never competes with the content:
//  1. a soft pool of light behind the content, falling off to darker edges;
//  2. two halftone dot fields at different depths, drifting slowly and only at the edges;
//  3. one giant ghost kanji for the scene, outlined, with an off-register copy behind it;
//  4. a still paper grain over everything.
// Nothing flashes and nothing moves faster than a few pixels a second.

const HalftoneField = ({
  id,
  cell,
  dot,
  color,
  speed,
  t,
  mask,
}: {
  readonly id: string;
  readonly cell: number;
  readonly dot: number;
  readonly color: string;
  readonly speed: [number, number];
  readonly t: number;
  readonly mask: string;
}) => {
  const dx = (speed[0] * t) % cell;
  const dy = (speed[1] * t) % cell;
  return (
    <svg
      width={1920}
      height={1080}
      style={{
        position: "absolute",
        inset: 0,
        maskImage: mask,
        WebkitMaskImage: mask,
      }}
    >
      <defs>
        <pattern
          id={id}
          width={cell}
          height={cell}
          patternUnits="userSpaceOnUse"
          patternTransform={`translate(${dx.toFixed(2)} ${dy.toFixed(2)}) rotate(30)`}
        >
          <circle cx={cell / 2} cy={cell / 2} r={dot} fill={color} />
        </pattern>
      </defs>
      <rect width={1920} height={1080} fill={`url(#${id})`} />
    </svg>
  );
};

const BackdropInner = ({
  kanji,
  style,
}: {
  readonly kanji: string;
  readonly style?: React.CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  // The ghost kanji drifts up slowly; its indigo plate sits 10px off, like misregistered print.
  const drift = -6 * t;
  const ghost: React.CSSProperties = {
    position: "absolute",
    right: 60,
    top: 40,
    writingMode: "vertical-rl",
    fontFamily: display,
    fontSize: 640,
    lineHeight: 1,
    color: "transparent",
    whiteSpace: "nowrap",
  };
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 75% 65% at 42% 45%, #2a2522 0%, #1e1b19 55%, #141210 100%)",
        }}
      />
      <HalftoneField
        id={`far${uid}`}
        cell={22}
        dot={2.2}
        color="#34506b"
        speed={[3, -2]}
        t={t}
        mask="radial-gradient(ellipse 70% 70% at 45% 45%, transparent 45%, rgba(0,0,0,0.55) 100%)"
      />
      <HalftoneField
        id={`near${uid}`}
        cell={34}
        dot={4}
        color="#c4472f"
        speed={[-6, 4]}
        t={t}
        mask="radial-gradient(ellipse 60% 60% at 45% 45%, transparent 60%, rgba(0,0,0,0.3) 100%)"
      />
      <div
        style={{
          ...ghost,
          translate: `10px ${(drift + 8).toFixed(2)}px`,
          WebkitTextStroke: "3px rgba(52, 80, 107, 0.35)",
        }}
      >
        {kanji}
      </div>
      <div
        style={{
          ...ghost,
          translate: `0px ${drift.toFixed(2)}px`,
          WebkitTextStroke: "3px rgba(237, 230, 218, 0.07)",
        }}
      >
        {kanji}
      </div>
      <svg
        width={1920}
        height={1080}
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.06,
          mixBlendMode: "overlay",
        }}
      >
        <filter id={`grain${uid}`}>
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            seed={7}
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width={1920} height={1080} filter={`url(#grain${uid})`} />
      </svg>
    </div>
  );
};

export const Backdrop = Interactive.create({
  Component: BackdropInner,
  layout: "none",
  schema: {
    kanji: {
      type: "string",
      default: "服",
      description: "Ghost kanji for the scene",
    },
  },
});
