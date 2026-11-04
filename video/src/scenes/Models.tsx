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

// Roles from the README's "Meta models used" table, cut to a few words each.
const MODELS: { name: string; role: string; color: string }[] = [
  { name: "SAM 3.1", role: "Cuts out every garment", color: "#c4472f" },
  {
    name: "MUSE SPARK 1.3",
    role: "Tags pieces, grades renders",
    color: "#6a8db2",
  },
  { name: "MUSE IMAGE", role: "Draws the optional try-on", color: "#e9b43c" },
  {
    name: "MUSE SPARK OPEN",
    role: "Plans your morning (via Baseten)",
    color: "#ede6da",
  },
];

// After the cards land, each takes a 1.4 s turn in the spotlight from 2.2 s: a slot per model
// for the voiceover. Only the lit card carries the red; the others dim a little.
const litFor = (i: number, frame: number, fps: number) => {
  const spot = (2.2 + i * 1.4) * fps;
  return interpolate(
    frame,
    [spot, spot + 0.4 * fps, spot + 1.1 * fps, spot + 1.4 * fps],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    },
  );
};

const ModelsInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const anyLit = Math.max(...MODELS.map((_, k) => litFor(k, frame, fps)));
  return (
    <>
      <Backdrop name="Backdrop" kanji="仕組み" />
      <Camera hits={[]}>
        <SceneText
          name="Models caption"
          kicker="UNDER THE HOOD · 仕組み · MODELS"
          title="BUILT ON META MODELS."
          body=""
          accent="#c4472f"
          delay={0}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />

        <Interactive.Div
          name="Model cards"
          style={{
            position: "absolute",
            left: 120,
            top: 340,
            width: 1680,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 40,
          }}
        >
          {MODELS.map((m, i) => {
            const at = (0.6 + i * 0.3) * fps;
            // Each card flips up into place like a sign being turned over.
            const flip = interpolate(frame, [at, at + 0.6 * fps], [90, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            });
            const lit = litFor(i, frame, fps);
            return (
              <div
                key={m.name}
                style={{
                  border: `3px solid ${lit > 0.5 ? "#d9573d" : "#ede6da"}`,
                  borderRadius: 20,
                  background: "#2c2825",
                  boxShadow: `${10 + lit * 8}px ${10 + lit * 8}px 0 ${m.color}`,
                  padding: "34px 40px",
                  opacity: frame < at ? 0 : 1,
                  // Dim the unlit cards by darkening, so the street never shows through them.
                  filter: `brightness(${(1 - 0.4 * Math.max(0, anyLit - lit)).toFixed(3)})`,
                  transform: `perspective(1400px) rotateX(${flip.toFixed(2)}deg) translateY(${(-14 * lit).toFixed(2)}px)`,
                  transformOrigin: "50% 0%",
                }}
              >
                <div
                  style={{
                    fontFamily: mono,
                    fontSize: 28,
                    letterSpacing: "0.12em",
                    color: "#a39a8e",
                  }}
                >
                  0{i + 1}
                </div>
                <div
                  style={{
                    fontFamily: display,
                    fontSize: 68,
                    lineHeight: 1.1,
                    marginTop: 6,
                  }}
                >
                  {m.name}
                </div>
                <div
                  style={{
                    fontFamily: body,
                    fontWeight: 700,
                    fontSize: 38,
                    marginTop: 12,
                    color: "#cfc7ba",
                  }}
                >
                  {m.role}
                </div>
              </div>
            );
          })}
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Models = Interactive.create({
  Component: ModelsInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
