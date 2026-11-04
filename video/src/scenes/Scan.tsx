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
import { Phone } from "../components/Phone";
import { SceneText } from "../components/SceneText";
import { Tap } from "../components/Tap";
import { body, display, mono } from "../theme";

// Real tags Muse Spark gave this piece (fixtures/sample_closet/closet.json).
const JEANS_TAGS: [string, string][] = [
  ["TYPE", "straight-leg jeans"],
  ["COLOUR", "dark blue"],
  ["FABRIC", "denim"],
  ["FIT", "slim straight"],
  ["SURE", "0.95"],
];

// Sample-closet cutouts that fly out of the phone and land in a fan under the headline.
const PIECES = [
  { id: "1f489bb28a9612c4", x: 110, y: 610, rot: -10 },
  { id: "dd97e86ca07806ef", x: 300, y: 590, rot: 6 },
  { id: "93c1d6bd6e24c05d", x: 490, y: 615, rot: -4 },
  { id: "d064b68b32a8366f", x: 660, y: 580, rot: 9 },
];

const ScanInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="服" />
      <Camera hits={[7.35, 8.1]}>
        <SceneText
          name="Scan caption"
          kicker="01 · FEED ME · 服をちょうだい"
          title="SNAP ONE PHOTO."
          body=""
          accent="#c4472f"
          delay={0.2}
          style={{ position: "absolute", left: 120, top: 150, width: 760 }}
        />

        <Interactive.Div
          name="Flying cutouts"
          style={{ position: "absolute", inset: 0 }}
        >
          {PIECES.map((p, i) => {
            const s = (6.9 + i * 0.15) * fps;
            const k = interpolate(frame, [s, s + 0.6 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.out(Easing.cubic),
            });
            // An arc from the phone screen to its place in the fan.
            const fromX = 1500;
            const fromY = 450;
            const x = fromX + (p.x - fromX) * k;
            const y = fromY + (p.y - fromY) * k - Math.sin(k * Math.PI) * 220;
            return (
              <Img
                key={p.id}
                src={staticFile(`assets/${p.id}.png`)}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  width: 210,
                  height: 210,
                  objectFit: "contain",
                  opacity: frame < s ? 0 : 1,
                  rotate: `${p.rot + (1 - k) * 200}deg`,
                  scale: String(0.4 + 0.6 * k),
                  filter:
                    "drop-shadow(0 0 2px #ede6da) drop-shadow(0 0 1px #ede6da) drop-shadow(6px 8px 0 rgba(0, 0, 0, 0.45))",
                }}
              />
            );
          })}
        </Interactive.Div>

        <Interactive.Div
          name="SAM sticker"
          style={{
            position: "absolute",
            left: 120,
            top: 860,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.1em",
            background: "#c4472f",
            color: "#ffffff",
            padding: "12px 22px",
            borderRadius: 8,
            rotate: "-3deg",
            opacity: interpolate(frame, [7.3 * fps, 7.45 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(frame, [7.3 * fps, 7.7 * fps], [1.8, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          SAM 3.1 · CUTS OUT EVERY PIECE
        </Interactive.Div>

        <Interactive.Div
          name="Tag card"
          style={{
            position: "absolute",
            left: 900,
            top: 280,
            width: 420,
            padding: 24,
            background: "#2c2825",
            border: "3px solid #ede6da",
            borderRadius: 18,
            boxShadow: "8px 8px 0 #34506b",
            rotate: interpolate(
              frame,
              [7.9 * fps, 8.4 * fps],
              ["14deg", "-3deg"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            opacity: interpolate(frame, [7.9 * fps, 8.1 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [7.9 * fps, 8.4 * fps],
              ["0px -260px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          <div
            style={{
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.1em",
              color: "#6a8db2",
              marginBottom: 12,
            }}
          >
            MUSE SPARK · TAGS
          </div>
          <div
            style={{
              display: "flex",
              gap: 16,
              alignItems: "center",
              marginBottom: 14,
            }}
          >
            <Img
              src={staticFile("assets/d064b68b32a8366f.png")}
              style={{
                width: 100,
                height: 100,
                objectFit: "contain",
                background: "#a79e91",
                borderRadius: 10,
                border: "2px solid #ede6da",
              }}
            />
            <div style={{ fontFamily: display, fontSize: 34, lineHeight: 1 }}>
              DARK BLUE JEANS
            </div>
          </div>
          {JEANS_TAGS.map(([k, v], i) => (
            <div
              key={k}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                padding: "7px 0",
                borderTop: "1.5px dashed #c9bfb0",
                fontFamily: body,
                fontSize: 28,
                opacity: interpolate(
                  frame,
                  [(8.5 + i * 0.18) * fps, (8.7 + i * 0.18) * fps],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                ),
                translate: `${interpolate(
                  frame,
                  [(8.5 + i * 0.18) * fps, (8.8 + i * 0.18) * fps],
                  [30, 0],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  },
                )}px 0px`,
              }}
            >
              <span
                style={{
                  fontFamily: mono,
                  fontSize: 26,
                  letterSpacing: "0.08em",
                  color: "#a39a8e",
                  paddingTop: 4,
                }}
              >
                {k}
              </span>
              <span style={{ fontWeight: 700, textAlign: "right" }}>{v}</span>
            </div>
          ))}
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
            translate: interpolate(
              frame,
              [0, 0.9 * fps],
              ["0px 160px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          <Phone
            screens={["05-closet-sample", "20-closet-full"]}
            index={interpolate(frame, [6.4 * fps, 6.9 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.7, 0, 0.2, 1),
            })}
            tabbar={frame > 6.6 * fps}
            enter={0}
            scale={0.96}
            zoom={interpolate(
              frame,
              [4.3 * fps, 5.1 * fps, 5.8 * fps, 6.5 * fps],
              [1, 1.5, 1.5, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            )}
            focus={[315, 824]}
            travel={[-306, -274]}
            spotlight
            scroll={interpolate(frame, [9.4 * fps, 12 * fps], [0, 454], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.inOut(Easing.cubic),
            })}
          >
            <Tap x={315} y={824} at={5.6} />
          </Phone>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Scan = Interactive.create({
  Component: ScanInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
