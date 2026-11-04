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

// The problem the oni eats: two figures from the Ellen MacArthur Foundation's report
// "A New Textiles Economy" (2017), credited on screen. Clothing utilisation (times a garment
// is worn before it stops being used) fell 36% in 15 years, and the equivalent of one garbage
// truck of textiles is landfilled or burned every second.
const CARDS: {
  label: string;
  value: number;
  sign: string;
  unit: string;
  text: string;
  at: number;
  hero?: boolean;
}[] = [
  {
    label: "WEARS PER GARMENT",
    value: 36,
    sign: "−",
    unit: "%",
    text: "Times a piece is worn before it's thrown out, vs 15 years earlier",
    at: 1,
    hero: true,
  },
  {
    label: "EVERY SECOND",
    value: 1,
    sign: "",
    unit: " TRUCK",
    text: "of clothes and textiles, landfilled or burned",
    at: 1.8,
  },
];

const SOURCE =
  "SOURCE · ELLEN MACARTHUR FOUNDATION, A NEW TEXTILES ECONOMY (2017)";
const SOURCE_AT = 2.5;

const StakesInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const typed = Math.floor(
    interpolate(
      frame,
      [SOURCE_AT * fps, (SOURCE_AT + 0.6) * fps],
      [0, SOURCE.length],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    ),
  );
  return (
    <>
      <Backdrop name="Backdrop" kanji="捨" />
      <Camera>
        <SceneText
          name="Stakes caption"
          kicker="THE PROBLEM · 問題 · FAST FASHION"
          title="WORN LESS. BINNED SOONER."
          body=""
          accent="#c4472f"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />

        <Interactive.Div
          name="Figures"
          style={{
            position: "absolute",
            left: 120,
            top: 430,
            width: 1680,
            display: "flex",
            gap: 60,
          }}
        >
          {CARDS.map((c, i) => {
            const s = c.at * fps;
            // The figure counts up from its baseline like a bar would (data easing, STYLE.md).
            const count = Math.round(
              interpolate(
                frame,
                [s + 0.2 * fps, s + 0.2 * fps + 20],
                [0, c.value],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.out(Easing.cubic),
                },
              ),
            );
            return (
              <div
                key={c.label}
                style={{
                  flex: 1,
                  border: "3px solid #ede6da",
                  borderRadius: 20,
                  background: c.hero ? "#ede6da" : "#2c2825",
                  color: c.hero ? "#2b2724" : "#ede6da",
                  boxShadow: c.hero
                    ? "10px 10px 0 #c4472f"
                    : "8px 8px 0 #ede6da",
                  padding: "30px 34px",
                  opacity: interpolate(frame, [s, s + 0.15 * fps], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                  translate: `0px ${interpolate(
                    frame,
                    [s, s + 0.5 * fps],
                    [-500, 0],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    },
                  )}px`,
                  rotate: `${interpolate(
                    frame,
                    [s, s + 0.5 * fps],
                    [i % 2 ? 12 : -12, 0],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    },
                  )}deg`,
                }}
              >
                <div
                  style={{
                    fontFamily: mono,
                    fontSize: 28,
                    letterSpacing: "0.1em",
                  }}
                >
                  {c.label}
                </div>
                <div
                  style={{
                    fontFamily: display,
                    fontSize: 130,
                    lineHeight: 1.05,
                    marginTop: 20,
                    // One accent per shot: only the hero figure is red.
                    color: c.hero ? "#c4472f" : undefined,
                  }}
                >
                  {c.sign}
                  {count}
                  <span style={{ fontSize: c.unit === "%" ? 130 : 60 }}>
                    {c.unit}
                  </span>
                </div>
                <div
                  style={{
                    fontFamily: body,
                    fontWeight: 700,
                    fontSize: 34,
                    lineHeight: 1.3,
                    marginTop: 8,
                  }}
                >
                  {c.text}
                </div>
              </div>
            );
          })}
        </Interactive.Div>

        <Interactive.Div
          name="Source"
          style={{
            position: "absolute",
            left: 120,
            top: 840,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.08em",
            color: "#a39a8e",
          }}
        >
          {SOURCE.slice(0, typed)}
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Stakes = Interactive.create({
  Component: StakesInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
