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
import { Stamp } from "../components/Stamp";
import { body, display, mono } from "../theme";

// score() from the app's "How the oni decided" trace (public/captures/14-trace.png).
const PARTS = [
  { key: "rescue", label: "RESCUE", color: "#c4472f" },
  { key: "occasion", label: "OCCASION", color: "#34506b" },
  { key: "colour", label: "COLOUR", color: "#e9b43c" },
  { key: "taste", label: "TASTE", color: "#a39a8e" },
] as const;

const LOOKS: {
  name: string;
  note: string;
  items: string[];
  total: number;
  parts: Record<(typeof PARTS)[number]["key"], number>;
}[] = [
  {
    name: "A · Rediscovered pick",
    note: "Jeans unworn 400 days",
    items: ["93c1d6bd6e24c05d", "d064b68b32a8366f", "dd97e86ca07806ef"],
    total: 4.5,
    parts: { rescue: 3.0, occasion: 0.8, colour: 0.9, taste: -0.2 },
  },
  {
    name: "B · Fresh mix",
    note: "Long-sleeve unworn 260 days",
    items: ["1f489bb28a9612c4", "03449856702dba5a", "dd97e86ca07806ef"],
    total: 4.0,
    parts: { rescue: 3.0, occasion: 0.8, colour: 0.6, taste: -0.4 },
  },
  {
    name: "C · Stretch",
    note: "Never worn together",
    items: ["1f489bb28a9612c4", "d064b68b32a8366f", "dd97e86ca07806ef"],
    total: 3.4,
    parts: { rescue: 3.0, occasion: -0.6, colour: 0.9, taste: 0.1 },
  },
];

const ZERO = 900; // x of the zero line
const PX = 155; // pixels per point

const ScoresInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="選" />
      <Camera hits={[6.6]}>
        <SceneText
          name="Scores caption"
          kicker="UNDER THE HOOD · 仕組み · score()"
          title="WHY LOOK A WON."
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />
        <Stamp
          name="Winner stamp"
          text="選"
          color="#c4472f"
          size={120}
          at={6.4}
          style={{ left: 1720, top: 290 }}
        />

        <Interactive.Div
          name="Score legend"
          style={{
            position: "absolute",
            left: ZERO,
            top: 350,
            display: "flex",
            gap: 30,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.08em",
            opacity: interpolate(frame, [1.2 * fps, 1.7 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {PARTS.map((p) => (
            <span
              key={p.key}
              style={{ display: "flex", alignItems: "center", gap: 10 }}
            >
              <span
                style={{
                  width: 22,
                  height: 22,
                  background: p.color,
                  border: "2px solid #ede6da",
                }}
              />
              {p.label}
            </span>
          ))}
        </Interactive.Div>

        <Interactive.Div
          name="Score rows"
          style={{
            position: "absolute",
            left: 0,
            top: 420,
            width: 1920,
            height: 560,
          }}
        >
          <div
            style={{
              position: "absolute",
              left: ZERO - 2,
              top: 0,
              width: 4,
              height: 520,
              background: "#ede6da",
            }}
          />
          {LOOKS.map((look, row) => {
            const start = (1.3 + row * 1.6) * fps;
            let pos = 0;
            let neg = 0;
            return (
              <div
                key={look.name}
                style={{
                  position: "absolute",
                  left: 0,
                  top: row * 180,
                  width: 1920,
                  height: 150,
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
                    top: 15,
                    display: "flex",
                    gap: 6,
                  }}
                >
                  {look.items.map((id) => (
                    <Img
                      key={id}
                      src={staticFile(`assets/${id}.png`)}
                      style={{
                        width: 82,
                        height: 82,
                        objectFit: "contain",
                        background: "#a79e91",
                        border: "2px solid #ede6da",
                        borderRadius: 8,
                      }}
                    />
                  ))}
                </div>
                <div
                  style={{
                    position: "absolute",
                    left: 400,
                    top: 12,
                    width: 380,
                    fontFamily: body,
                    fontWeight: 700,
                    fontSize: 34,
                    lineHeight: 1.15,
                  }}
                >
                  {look.name}
                  <div
                    style={{
                      fontWeight: 400,
                      fontSize: 28,
                      color: "#a39a8e",
                      marginTop: 6,
                    }}
                  >
                    {look.note}
                  </div>
                </div>
                {PARTS.map((p, i) => {
                  const v = look.parts[p.key];
                  const grow = interpolate(
                    frame,
                    // Data story: each segment grows from the baseline in 20 frames, ease-out.
                    [
                      start + (0.3 + i * 0.35) * fps,
                      start + (0.3 + i * 0.35) * fps + 20,
                    ],
                    [0, 1],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.out(Easing.cubic),
                    },
                  );
                  const w = Math.abs(v) * PX;
                  const left = v >= 0 ? ZERO + pos : ZERO - neg - w;
                  if (v >= 0) pos += w;
                  else neg += w;
                  return (
                    <div
                      key={p.key}
                      style={{
                        position: "absolute",
                        left: v >= 0 ? left : left + w * (1 - grow),
                        top: 22,
                        width: w * grow,
                        height: 70,
                        background: p.color,
                        border: grow > 0 ? "2px solid #ede6da" : "none",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        overflow: "hidden",
                        fontFamily: mono,
                        fontSize: 28,
                        color: p.key === "colour" ? "#2b2724" : "#ffffff",
                      }}
                    >
                      {w > 60 &&
                        `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}`}
                    </div>
                  );
                })}
                <div
                  style={{
                    position: "absolute",
                    left: ZERO + pos + 24,
                    top: 18,
                    fontFamily: display,
                    fontSize: 64,
                    lineHeight: 1.2,
                    color: row === 0 ? "#d9573d" : "#ede6da",
                    opacity: interpolate(
                      frame,
                      [start + 1.8 * fps, start + 2.1 * fps],
                      [0, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                      },
                    ),
                  }}
                >
                  {look.total.toFixed(1)}
                </div>
              </div>
            );
          })}
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Scores = Interactive.create({
  Component: ScoresInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
