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
import tee from "../data/tee-hull.json";
import { body, display, mono } from "../theme";

// The tee's outline and convex hull were measured from the sample cutout the way
// closet/scan.py's shape_notes() does it (see src/data/tee-hull.json).
const HULL = tee.hull.map(([x, y]) => `${x},${y}`).join(" ");
const PERIMETER = tee.hull.reduce((sum, [x, y], i) => {
  const [nx, ny] = tee.hull[(i + 1) % tee.hull.length];
  return sum + Math.hypot(nx - x, ny - y);
}, 0);
const FILL = Math.round(tee.solidity * 100);

// The scale under the shapes runs from 50% to 100% of the hull filled.
const AT = (pct: number) => `${((pct - 50) / 50) * 100}%`;

const ShapeInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="形" />
      <Camera hits={[4.9, 6.8]}>
        <SceneText
          name="Shape caption"
          kicker="UNDER THE HOOD · 仕組み · SHAPE CHECK"
          title="T-SHIRT OR BANDANA?"
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 80, width: 1680 }}
        />

        <Interactive.Div
          name="Tee with hull"
          style={{
            position: "absolute",
            left: 200,
            top: 380,
            width: 461,
            height: 428,
            // A light photo slot behind the black tee, so it shows on the dark ground.
            background: "#e6dfd2",
            borderRadius: 24,
            boxShadow: "0 0 0 26px #e6dfd2, 10px 10px 0 30px #d9573d",
            opacity: interpolate(frame, [1 * fps, 1.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [1 * fps, 1.6 * fps],
              ["-700px 0px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            rotate: interpolate(
              frame,
              [1 * fps, 1.6 * fps],
              ["-40deg", "0deg"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          <svg
            viewBox={`0 0 ${tee.width} ${tee.height}`}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              overflow: "visible",
            }}
          >
            <polygon
              points={HULL}
              fill="#c4472f"
              opacity={interpolate(frame, [3 * fps, 3.4 * fps], [0, 0.55], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
            />
          </svg>
          <Img
            src={staticFile("assets/04928617f29c4d83.png")}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
            }}
          />
          <svg
            viewBox={`0 0 ${tee.width} ${tee.height}`}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              overflow: "visible",
            }}
          >
            <polygon
              points={HULL}
              fill="none"
              stroke="#2b2724"
              strokeWidth={4}
              strokeLinejoin="round"
              strokeDasharray={PERIMETER}
              strokeDashoffset={interpolate(
                frame,
                [1.6 * fps, 3 * fps],
                [PERIMETER, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.inOut(Easing.cubic),
                },
              )}
            />
          </svg>
        </Interactive.Div>
        <Interactive.Div
          name="Tee fill"
          style={{
            position: "absolute",
            left: 710,
            top: 480,
            color: "#ede6da",
            opacity: interpolate(frame, [3.1 * fps, 3.4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <div style={{ fontFamily: display, fontSize: 120, lineHeight: 1 }}>
            {Math.round(
              interpolate(frame, [3.1 * fps, 4.1 * fps], [0, FILL], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            )}
            %
          </div>
          <div
            style={{
              fontFamily: body,
              fontWeight: 700,
              fontSize: 32,
              width: 300,
              lineHeight: 1.25,
              marginTop: 10,
            }}
          >
            of its hull. The red is the notches.
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Bandana square"
          style={{
            position: "absolute",
            left: 1080,
            top: 410,
            width: 300,
            height: 300,
            rotate: "8deg",
            borderRadius: 6,
            border: "4px solid #ede6da",
            background:
              "radial-gradient(circle, #f3eee5 22%, transparent 24%) 0 0 / 34px 34px, #34506b",
            // Falls flat onto the page like a dropped scarf.
            opacity: interpolate(frame, [4.6 * fps, 4.7 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(
              frame,
              [4.6 * fps, 4.9 * fps, 5.1 * fps],
              [2.2, 0.94, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.out(Easing.quad),
                output: "perceptual-scale",
              },
            ),
          }}
        />
        <Interactive.Div
          name="Bandana fill"
          style={{
            position: "absolute",
            left: 1430,
            top: 480,
            color: "#ede6da",
            opacity: interpolate(frame, [5.2 * fps, 5.6 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <div style={{ fontFamily: display, fontSize: 96, lineHeight: 1.1 }}>
            ~100%
          </div>
          <div
            style={{
              fontFamily: body,
              fontWeight: 700,
              fontSize: 32,
              width: 340,
              lineHeight: 1.25,
              marginTop: 10,
            }}
          >
            A flat square has no notches.
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Fill scale"
          style={{
            position: "absolute",
            left: 120,
            top: 850,
            width: 1680,
            height: 26,
            border: "3px solid #ede6da",
            borderRadius: 13,
            background: "#2c2825",
            opacity: interpolate(frame, [6 * fps, 6.4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: AT(60),
              width: `calc(${AT(90)} - ${AT(60)})`,
              background: "#34506b",
            }}
          />
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: AT(95),
              right: 0,
              background: "#c4472f",
              borderRadius: "0 10px 10px 0",
            }}
          />
          {[50, 60, 70, 80, 90, 100].map((p) => (
            <div
              key={p}
              style={{
                position: "absolute",
                left: AT(p),
                top: 34,
                translate: "-50% 0px",
                fontFamily: mono,
                fontSize: 28,
                color: "#a39a8e",
              }}
            >
              {p}%
            </div>
          ))}
          <div
            style={{
              position: "absolute",
              left: AT(75),
              top: -52,
              translate: "-50% 0px",
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.08em",
              color: "#6a8db2",
              whiteSpace: "nowrap",
            }}
          >
            TOPS & TROUSERS 60–90%
          </div>
          <div
            style={{
              position: "absolute",
              right: 0,
              top: -52,
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.08em",
              color: "#c4472f",
              whiteSpace: "nowrap",
            }}
          >
            FLAT FABRIC 95%+
          </div>
          <div
            style={{
              position: "absolute",
              left: AT(tee.solidity * 100),
              top: -16,
              width: 8,
              height: 52,
              background: "#ede6da",
              borderRadius: 4,
              opacity: interpolate(frame, [6.5 * fps, 6.6 * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
              // Drops onto the scale and settles on the tee's measured 87%.
              translate: `-50% ${interpolate(
                frame,
                [6.5 * fps, 6.8 * fps],
                [-260, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.16, 1, 0.3, 1),
                },
              )}px`,
            }}
          />
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Shape = Interactive.create({
  Component: ShapeInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
