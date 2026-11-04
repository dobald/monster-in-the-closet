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
import { body, display, mono } from "../theme";

// Judge scores (1–5) before and after each try-on fix, from the README's Day-0 findings.
const ROWS: { what: string; fix: string; before: number; after: number }[] = [
  {
    what: "Tour tee back print, on a person",
    fix: "TAGS: WHICH SIDE THE PRINT IS ON",
    before: 1,
    after: 5,
  },
  {
    what: "Tour tee back print, mannequin",
    fix: "TAGS: WHICH SIDE THE PRINT IS ON",
    before: 3,
    after: 5,
  },
  { what: "Baggy jeans keep their cut", fix: "TAGS: FIT", before: 2, after: 4 },
  {
    what: "Jeans keep their wash",
    fix: "COLOUR MEASURED FROM THE PHOTO",
    before: 2,
    after: 4,
  },
  {
    what: "One outfit, redone with notes",
    fix: "SELF-CORRECTION UNDER 4/5",
    before: 3,
    after: 4,
  },
];

const BAR_X = 860;
const PT = 130; // pixels per point

const RendersInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="試着" />
      <Camera hits={[1.2 + (ROWS.length - 1) * 0.75 + 1]}>
        <SceneText
          name="Renders caption"
          kicker="UNDER THE HOOD · 仕組み · TRY-ON"
          title="RENDERS GET GRADED."
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />
        <Interactive.Div
          name="Judge sticker"
          style={{
            position: "absolute",
            left: 120,
            top: 300,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.08em",
            background: "#34506b",
            color: "#f3eee5",
            padding: "10px 18px",
            borderRadius: 8,
            rotate: "-1.5deg",
            scale: interpolate(frame, [1.1 * fps, 1.4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          MUSE IMAGE DRAWS · MUSE SPARK SCORES 1–5 · UNDER 4 IS REDONE
        </Interactive.Div>

        <Interactive.Div
          name="Render rows"
          style={{
            position: "absolute",
            left: 0,
            top: 410,
            width: 1920,
            height: 580,
          }}
        >
          {ROWS.map((r, i) => {
            const start = (1.2 + i * 0.75) * fps;
            return (
              <div
                key={r.what}
                style={{
                  position: "absolute",
                  left: 0,
                  top: i * 112,
                  width: 1920,
                  height: 100,
                  opacity: interpolate(
                    frame,
                    [start, start + 0.4 * fps],
                    [0, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                  ),
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: 120,
                    top: 8,
                    width: 700,
                  }}
                >
                  <div
                    style={{ fontFamily: body, fontWeight: 700, fontSize: 34 }}
                  >
                    {r.what}
                  </div>
                  <div
                    style={{
                      fontFamily: mono,
                      fontSize: 28,
                      letterSpacing: "0.08em",
                      color: "#a39a8e",
                      marginTop: 6,
                    }}
                  >
                    {r.fix}
                  </div>
                </div>
                <div
                  style={{
                    position: "absolute",
                    left: BAR_X,
                    top: 18,
                    width: 5 * PT,
                    height: 56,
                    border: "3px solid #ede6da",
                    borderRadius: 8,
                    background: "#2c2825",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: BAR_X,
                    top: 18,
                    height: 56,
                    borderRadius: 8,
                    border: "3px solid #ede6da",
                    background: "#c4472f",
                    width: interpolate(
                      frame,
                      [start + 0.6 * fps, start + 1.1 * fps],
                      [r.before * PT, r.after * PT],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.out(Easing.cubic),
                      },
                    ),
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: BAR_X,
                    top: 18,
                    height: 56,
                    width: r.before * PT,
                    borderRadius: 8,
                    border: "3px solid #ede6da",
                    background: "#c9bfb0",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: BAR_X + 5 * PT + 30,
                    top: 12,
                    fontFamily: display,
                    fontSize: 56,
                    color: "#ede6da",
                  }}
                >
                  {r.before} →{" "}
                  <span
                    style={{
                      display: "inline-block",
                      color: "#c4472f",
                      scale: String(
                        interpolate(
                          frame,
                          [start + 1 * fps, start + 1.3 * fps],
                          [0, 1],
                          {
                            extrapolateLeft: "clamp",
                            extrapolateRight: "clamp",
                            easing: Easing.bezier(0.16, 1, 0.3, 1),
                          },
                        ),
                      ),
                    }}
                  >
                    {r.after}
                  </span>
                  <span
                    style={{ fontFamily: mono, fontSize: 28, color: "#a39a8e" }}
                  >
                    {" "}
                    /5
                  </span>
                </div>
              </div>
            );
          })}
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Renders = Interactive.create({
  Component: RendersInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
