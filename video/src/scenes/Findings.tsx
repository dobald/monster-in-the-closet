import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop } from "../components/Backdrop";
import { Camera } from "../components/Camera";
import { SceneText } from "../components/SceneText";
import { Stamp } from "../components/Stamp";
import { body, display, mono } from "../theme";

// The README's "Day-0 findings (real closet, ~$1.60 total)" table.
const RUNS: {
  how: string;
  usable: number;
  of: number;
  time: string;
  win?: boolean;
}[] = [
  { how: "RAIL PAN VIDEO", usable: 5, of: 25, time: "~27 MIN" },
  { how: "FLICK-THROUGH VIDEO", usable: 9, of: 16, time: "39 MIN" },
  { how: "FLAT-LAY PHOTO", usable: 4, of: 4, time: "~15 S", win: true },
];

const FindingsInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="撮る" />
      <Camera hits={[4.1, 5.2]}>
        <SceneText
          name="Findings caption"
          kicker="UNDER THE HOOD · 仕組み · DAY 0"
          title="THREE WAYS TO SCAN A REAL CLOSET."
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />

        <Interactive.Div
          name="Findings cards"
          style={{
            position: "absolute",
            left: 120,
            top: 420,
            width: 1680,
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 48,
          }}
        >
          {RUNS.map((r, i) => {
            const s = (0.9 + i * 0.9) * fps;
            const count = Math.round(
              interpolate(frame, [s + 0.3 * fps, s + 1 * fps], [0, r.usable], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            );
            // The two video runs sag once the winner lands.
            const sag = r.win
              ? 0
              : interpolate(frame, [4.1 * fps, 4.6 * fps], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
            return (
              <div
                key={r.how}
                style={{
                  position: "relative",
                  border: "3px solid #ede6da",
                  borderRadius: 20,
                  background: r.win ? "#ede6da" : "#2c2825",
                  color: r.win ? "#2b2724" : "#ede6da",
                  boxShadow: r.win
                    ? "10px 10px 0 #c4472f"
                    : "8px 8px 0 #ede6da",
                  padding: "30px 34px",
                  opacity:
                    interpolate(frame, [s, s + 0.15 * fps], [0, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                    }) *
                    (1 - 0.45 * sag),
                  translate: `0px ${
                    interpolate(frame, [s, s + 0.5 * fps], [-500, 0], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    }) +
                    sag * 24
                  }px`,
                  rotate: `${
                    interpolate(
                      frame,
                      [s, s + 0.5 * fps],
                      [i % 2 ? 12 : -12, 0],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.bezier(0.16, 1, 0.3, 1),
                      },
                    ) +
                    sag * (i % 2 ? 2 : -2)
                  }deg`,
                }}
              >
                <div
                  style={{
                    fontFamily: mono,
                    fontSize: 28,
                    letterSpacing: "0.1em",
                  }}
                >
                  {r.how}
                </div>
                <div
                  style={{
                    fontFamily: display,
                    fontSize: 130,
                    lineHeight: 1.05,
                    marginTop: 20,
                  }}
                >
                  {count}
                  <span style={{ fontSize: 60, opacity: 0.6 }}> /{r.of}</span>
                </div>
                <div
                  style={{
                    fontFamily: body,
                    fontWeight: 700,
                    fontSize: 34,
                    marginTop: 8,
                  }}
                >
                  {r.time}
                </div>
              </div>
            );
          })}
        </Interactive.Div>

        <Stamp
          name="Winner stamp"
          text="選"
          color="#c4472f"
          size={150}
          at={3.9}
          style={{ left: 1690, top: 370 }}
        />

        <Interactive.Div
          name="Cost sticker"
          style={{
            position: "absolute",
            left: 120,
            top: 880,
            fontFamily: mono,
            fontSize: 30,
            letterSpacing: "0.1em",
            background: "#e9b43c",
            color: "#2b2724",
            border: "3px solid #2b2724",
            padding: "12px 22px",
            borderRadius: 8,
            rotate: "-2deg",
            opacity: interpolate(frame, [5 * fps, 5.15 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(frame, [5 * fps, 5.4 * fps], [1.8, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          THE WHOLE DAY OF TESTS: ~$1.60
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Findings = Interactive.create({
  Component: FindingsInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
