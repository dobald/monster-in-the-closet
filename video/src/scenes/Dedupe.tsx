import {
  Easing,
  Img,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop } from "../components/Backdrop";
import { Camera } from "../components/Camera";
import { SceneText } from "../components/SceneText";
import { body, display, mono } from "../theme";

// The README's "Same garment, different photos" pipeline and its run on the 11-item test closet.
const STEPS: { n: string; title: string; text: string; out: string }[] = [
  {
    n: "1",
    title: "SHORTLIST",
    text: "Close colour, different photos",
    out: "13 PAIRS",
  },
  {
    n: "2",
    title: "JUDGE",
    text: "Muse Spark compares both",
    out: "13 / 13 RIGHT",
  },
  {
    n: "3",
    title: "ACT",
    text: "Sure? Merge. Unsure? Ask you.",
    out: "≥ 0.85 MERGES",
  },
];

const RESULTS = [
  "Sweatshirt ×2 → 1",
  "Tour tee ×2 → 1",
  "Track pants ×3 → 1",
  "Henley ≠ tour tee",
];

const DedupeInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Two "photos" of the same tee (an illustration with a sample cutout) slide together and merge.
  const merge = interpolate(frame, [4.2 * fps, 4.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  const merged = frame >= 4.9 * fps;
  return (
    <>
      <Backdrop name="Backdrop" kanji="同じ" />
      <Camera hits={[4.9]}>
        <SceneText
          name="Dedupe caption"
          kicker="UNDER THE HOOD · 仕組み · DUPLICATES"
          title="SHOT TWICE? ONE ITEM."
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />

        <Interactive.Div
          name="Dedupe steps"
          style={{
            position: "absolute",
            left: 120,
            top: 330,
            width: 1680,
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 60,
          }}
        >
          {STEPS.map((s, i) => {
            const at = (0.9 + i * 0.8) * fps;
            return (
              <div
                key={s.n}
                style={{
                  position: "relative",
                  border: "3px solid #ede6da",
                  borderRadius: 20,
                  background: "#2c2825",
                  boxShadow: "8px 8px 0 #ede6da",
                  padding: "26px 30px",
                  opacity: interpolate(frame, [at, at + 0.15 * fps], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                  scale: String(
                    interpolate(frame, [at, at + 0.4 * fps], [0.5, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    }),
                  ),
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: 28,
                      background: "#ede6da",
                      color: "#2b2724",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: display,
                      fontSize: 30,
                    }}
                  >
                    {s.n}
                  </span>
                  <span style={{ fontFamily: display, fontSize: 52 }}>
                    {s.title}
                  </span>
                </div>
                <div
                  style={{
                    fontFamily: body,
                    fontWeight: 700,
                    fontSize: 34,
                    lineHeight: 1.25,
                    marginTop: 18,
                    minHeight: 90,
                    color: "#cfc7ba",
                  }}
                >
                  {s.text}
                </div>
                <div
                  style={{
                    display: "inline-block",
                    fontFamily: mono,
                    fontSize: 28,
                    letterSpacing: "0.08em",
                    background: i === 2 ? "#c4472f" : "#34506b",
                    color: "#ffffff",
                    padding: "8px 14px",
                    borderRadius: 6,
                    rotate: "-2deg",
                    scale: String(
                      interpolate(
                        frame,
                        [at + 0.5 * fps, at + 0.8 * fps],
                        [0, 1],
                        {
                          extrapolateLeft: "clamp",
                          extrapolateRight: "clamp",
                          easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                        },
                      ),
                    ),
                  }}
                >
                  {s.out}
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    style={{
                      position: "absolute",
                      right: -54,
                      top: "40%",
                      fontFamily: display,
                      fontSize: 52,
                      color: "#c4472f",
                      translate: `${Math.sin((frame / fps) * 6) * 5}px 0px`,
                    }}
                  >
                    →
                  </div>
                )}
              </div>
            );
          })}
        </Interactive.Div>

        <Interactive.Div
          name="Merge demo"
          style={{
            position: "absolute",
            left: 120,
            top: 700,
            width: 620,
            height: 280,
          }}
        >
          {[0, 1].map((k) => (
            <div
              key={k}
              style={{
                position: "absolute",
                top: 20,
                left: k === 0 ? merge * 150 : 300 - merge * 150,
                width: 200,
                height: 230,
                padding: 14,
                // Photos stay light, like the app's screens, so the black tee shows.
                background: "#f3eee5",
                color: "#2b2724",
                border: "3px solid #ede6da",
                boxShadow: "6px 6px 0 #c4472f",
                rotate: `${(k ? 6 : -5) * (1 - merge)}deg`,
                opacity:
                  merged && k === 1
                    ? 0
                    : interpolate(frame, [3.6 * fps, 3.8 * fps], [0, 1], {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                      }),
                scale: merged
                  ? String(
                      interpolate(frame, [4.9 * fps, 5.2 * fps], [1.25, 1], {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                      }),
                    )
                  : "1",
              }}
            >
              <Img
                src={staticFile("assets/04928617f29c4d83.png")}
                style={{ width: "100%", height: 150, objectFit: "contain" }}
              />
              <div
                style={{
                  fontFamily: mono,
                  fontSize: 28,
                  letterSpacing: "0.08em",
                  marginTop: 12,
                }}
              >
                {merged ? "ONE ITEM" : `PHOTO ${k + 1}`}
              </div>
            </div>
          ))}
          <div
            style={{
              position: "absolute",
              left: 400,
              top: 70,
              fontFamily: display,
              fontSize: 110,
              color: "#c4472f",
              opacity: merged ? 1 : 0,
              scale: String(
                interpolate(frame, [4.9 * fps, 5.2 * fps], [2, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                }),
              ),
            }}
          >
            =1
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Dedupe count"
          style={{
            position: "absolute",
            left: 820,
            top: 700,
            color: "#ede6da",
          }}
        >
          <div
            style={{
              fontFamily: display,
              fontSize: 120,
              lineHeight: 1.05,
              opacity: interpolate(frame, [5.4 * fps, 5.6 * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            11 →{" "}
            {Math.round(
              interpolate(frame, [5.6 * fps, 6.6 * fps], [11, 7], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            )}
            <span style={{ fontSize: 48 }}> ITEMS</span>
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              marginTop: 14,
              width: 980,
            }}
          >
            {RESULTS.map((r, i) => (
              <span
                key={r}
                style={{
                  fontFamily: mono,
                  fontSize: 28,
                  letterSpacing: "0.04em",
                  padding: "10px 16px",
                  borderRadius: 999,
                  border: "3px solid #ede6da",
                  background: i === 3 ? "#34506b" : "#2c2825",
                  color: i === 3 ? "#f3eee5" : "#ede6da",
                  opacity: interpolate(
                    frame,
                    [(6.6 + i * 0.2) * fps, (6.75 + i * 0.2) * fps],
                    [0, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                  ),
                  translate: `0px ${interpolate(
                    frame,
                    [(6.6 + i * 0.2) * fps, (7 + i * 0.2) * fps],
                    [30, 0],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    },
                  )}px`,
                }}
              >
                {r}
              </span>
            ))}
          </div>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Dedupe = Interactive.create({
  Component: DedupeInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
