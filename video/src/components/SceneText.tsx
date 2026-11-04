import type React from "react";
import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { body as bodyFont, display, mono } from "../theme";

// A scene's caption block: the kicker types itself out, then the headline drops in word by
// word with a springy overshoot, and an ink bar swipes in under it. `body` is optional and
// left empty in most scenes, so a voiceover can carry the detail.
const SceneTextInner = ({
  kicker,
  title,
  body,
  accent,
  delay,
  style,
}: {
  readonly kicker: string;
  readonly title: string;
  readonly body: string;
  readonly accent: string;
  readonly delay: number;
  readonly style?: React.CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const at = delay * fps;
  const typed = Math.floor(
    interpolate(frame, [at, at + 0.6 * fps], [0, kicker.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const words = title.split(" ");
  const wordsAt = at + 0.35 * fps;
  // Words stagger by 3 frames and each rise takes 21 (STYLE.md).
  const STAGGER = 3;
  const RISE = 21;
  const done = wordsAt + words.length * STAGGER + RISE;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 26,
        color: "#ede6da",
        ...style,
      }}
    >
      <div
        style={{
          fontFamily: mono,
          fontSize: 28,
          letterSpacing: "0.12em",
          // The kicker stays muted; the accent marks only the underline, one accent per shot.
          color: "#a39a8e",
          minHeight: 34,
          // A halo of the dark ground keeps small text readable over the neon signs.
          textShadow: "0 0 6px #1e1b19, 0 0 12px #1e1b19, 0 0 2px #1e1b19",
        }}
      >
        {kicker.slice(0, typed)}
        {typed < kicker.length && typed > 0 && (
          <span style={{ opacity: 0.6 }}>▌</span>
        )}
      </div>
      <div
        style={{
          fontFamily: display,
          fontSize: 96,
          lineHeight: 0.98,
          letterSpacing: "-0.01em",
        }}
      >
        {words.map((w, i) => {
          const s = wordsAt + i * STAGGER;
          // Each word rises out of its own mask: a clip reveal, never a fade.
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                overflow: "hidden",
                verticalAlign: "top",
                padding: "0.06em 0.02em",
                margin: "-0.06em 0.22em -0.06em -0.02em",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  translate: `0px ${interpolate(
                    frame,
                    [s, s + RISE],
                    [110, 0],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    },
                  )}%`,
                }}
              >
                {w}
              </span>
            </span>
          );
        })}
      </div>
      <div
        style={{
          height: 10,
          borderRadius: 5,
          background: accent,
          width: interpolate(frame, [done, done + 0.4 * fps], [0, 220], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      />
      {body && (
        <div
          style={{
            fontFamily: bodyFont,
            fontSize: 44,
            lineHeight: 1.3,
            color: "#cfc7ba",
            opacity: interpolate(frame, [done, done + 0.5 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {body}
        </div>
      )}
    </div>
  );
};

export const SceneText = Interactive.create({
  Component: SceneTextInner,
  layout: "none",
  schema: {
    ...Interactive.textSchema,
    kicker: { type: "string", default: "01 · STEP", description: "Kicker" },
    title: { type: "string", default: "HEADLINE", description: "Headline" },
    body: { type: "string", default: "", description: "Supporting line" },
    accent: { type: "color", default: "#c4472f", description: "Kicker colour" },
    delay: {
      type: "number",
      default: 0,
      min: 0,
      step: 0.1,
      description: "Entrance delay (s)",
      hiddenFromList: false,
    },
  },
});
