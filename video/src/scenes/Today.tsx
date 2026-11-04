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

// Why the oni picked look A, as stickers that slap on one after another.
const REASONS = [
  {
    label: "FEELS LIKE 3° → JACKET",
    color: "#34506b",
    ink: "#f3eee5",
    at: 2.4,
    rot: -3,
  },
  {
    label: "10:00 CRIT → SMART CASUAL",
    color: "#34506b",
    ink: "#f3eee5",
    at: 3.1,
    rot: 2,
  },
  {
    label: "400日 UNWORN → TODAY'S HERO",
    color: "#c4472f",
    ink: "#ffffff",
    at: 3.8,
    rot: -2,
  },
];

const TodayInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const swipe = (from: number) =>
    interpolate(frame, [from * fps, (from + 0.5) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // Screen changes snap (STYLE.md).
      easing: Easing.bezier(0.7, 0, 0.2, 1),
    });
  return (
    <>
      <Backdrop name="Backdrop" kanji="今日" />
      <Camera hits={[3.8]}>
        <SceneText
          name="Today caption"
          kicker="03 · EVERY MORNING · 今日のコーデ"
          title="DRESSED IN WHAT YOU ALREADY OWN."
          body=""
          accent="#c4472f"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 150, width: 1000 }}
        />

        <Interactive.Div
          name="Reasons"
          style={{
            position: "absolute",
            left: 120,
            top: 640,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            gap: 22,
          }}
        >
          {REASONS.map((r) => (
            <span
              key={r.label}
              style={{
                fontFamily: mono,
                fontSize: 32,
                letterSpacing: "0.06em",
                background: r.color,
                color: r.ink,
                border: "3px solid #ede6da",
                boxShadow: "5px 5px 0 #ede6da",
                padding: "12px 20px",
                borderRadius: 8,
                rotate: `${r.rot}deg`,
                opacity: interpolate(
                  frame,
                  [r.at * fps, (r.at + 0.08) * fps],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                ),
                scale: String(
                  interpolate(
                    frame,
                    [r.at * fps, (r.at + 0.35) * fps],
                    [1.9, 1],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                    },
                  ),
                ),
              }}
            >
              {r.label}
            </span>
          ))}
        </Interactive.Div>

        <Interactive.Div
          name="Swipe hint"
          style={{
            position: "absolute",
            left: 1000,
            top: 520,
            fontFamily: mono,
            fontSize: 30,
            letterSpacing: "0.1em",
            color: "#ede6da",
            opacity: interpolate(
              frame,
              [5 * fps, 5.2 * fps, 9 * fps, 9.4 * fps],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
            translate: `${Math.sin((frame / fps) * 5) * 12}px 0px`,
          }}
        >
          SWIPE ›
        </Interactive.Div>

        <Interactive.Div
          name="Phone"
          style={{
            position: "absolute",
            left: 1370,
            top: 70,
            opacity: interpolate(frame, [0, 0.3 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <Phone
            screens={["10-today", "11-today-look2", "12-today-look3"]}
            index={swipe(5.8) + swipe(8)}
            enter={0}
            scale={0.96}
            zoom={interpolate(
              frame,
              [1.8 * fps, 2.6 * fps, 4.3 * fps, 5 * fps],
              [1, 1.5, 1.5, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            )}
            focus={[183, 426]}
            travel={[-180, 28]}
          >
            <Tap x={374} y={731} at={5.5} />
            <Tap x={374} y={731} at={7.7} />
          </Phone>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Today = Interactive.create({
  Component: TodayInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
