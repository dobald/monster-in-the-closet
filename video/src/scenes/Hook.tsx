import {
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop } from "../components/Backdrop";
import { Camera } from "../components/Camera";
import { Oni } from "../Oni";
import { body, display, mono } from "../theme";

const WORDS = [
  "THIS",
  "ONE",
  "STARVES",
  "WHEN",
  "YOUR",
  "CLOTHES",
  "GO",
  "UNWORN.",
];
// When the headline starts rising, in seconds. "STARVES" lands about 9 frames after its turn.
const HEADLINE_AT = 1.75; // so "STARVES" lands on beat 3

const HookInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="鬼" />
      <Camera hits={[0.96, HEADLINE_AT + 0.5]}>
        <Interactive.Div
          name="Brand label"
          style={{
            position: "absolute",
            left: 120,
            top: 100,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.12em",
            color: "#ede6da",
            opacity: interpolate(frame, [0, 0.4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          MONSTER IN THE CLOSET · 東京
        </Interactive.Div>

        <Interactive.Div
          name="Setup line"
          style={{
            position: "absolute",
            left: 120,
            top: 250,
            width: 1150,
            fontFamily: body,
            fontWeight: 700,
            fontSize: 56,
            lineHeight: 1.15,
            color: "#cfc7ba",
            opacity: interpolate(frame, [1.01 * fps, 1.41 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [1.01 * fps, 1.71 * fps],
              ["-60px 0px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          Every closet app wants to style you.
        </Interactive.Div>

        <Interactive.Div
          name="Hook headline"
          style={{
            position: "absolute",
            left: 120,
            top: 370,
            width: 1100,
            fontFamily: display,
            fontSize: 112,
            lineHeight: 0.95,
            color: "#ede6da",
          }}
        >
          {WORDS.map((w, i) => {
            // 3-frame stagger, with a 10-frame beat after the hero word so it lands alone.
            const s = HEADLINE_AT * fps + i * 3 + (i > 2 ? 10 : 0);
            const hero = w === "STARVES";
            return (
              <span
                key={w}
                style={{
                  display: "inline-block",
                  overflow: hero ? "visible" : "hidden",
                  verticalAlign: "top",
                  padding: "0.06em 0.02em",
                  margin: "-0.06em 0.2em -0.06em -0.02em",
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    color: hero ? "#d9573d" : "#ede6da",
                    translate: hero
                      ? "0px 0px"
                      : `0px ${interpolate(frame, [s, s + 21], [110, 0], {
                          extrapolateLeft: "clamp",
                          extrapolateRight: "clamp",
                          easing: Easing.bezier(0.16, 1, 0.3, 1),
                        })}%`,
                    // The hero word is the hook's one pop: it slams down from large.
                    opacity: hero
                      ? interpolate(frame, [s, s + 2], [0, 1], {
                          extrapolateLeft: "clamp",
                          extrapolateRight: "clamp",
                        })
                      : 1,
                    scale: hero
                      ? String(
                          interpolate(frame, [s, s + 9], [2.4, 1], {
                            extrapolateLeft: "clamp",
                            extrapolateRight: "clamp",
                            easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                          }),
                        )
                      : "1",
                    rotate: hero ? "-3deg" : "0deg",
                  }}
                >
                  {w}
                </span>
              </span>
            );
          })}
        </Interactive.Div>

        <Interactive.Div
          name="Oni"
          style={{
            position: "absolute",
            right: 160,
            top: 260,
            // The hook, inside the first second: it falls (stretched into a smear), lands,
            // squashes flat and springs back.
            translate: interpolate(
              frame,
              [0.56 * fps, 0.96 * fps],
              ["0px -1100px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.in(Easing.quad),
              },
            ),
            scale: interpolate(
              frame,
              [0.56 * fps, 0.94 * fps, 0.96 * fps, 1.03 * fps, 1.41 * fps],
              ["0.86 1.22", "0.86 1.22", "1.24 0.74", "1.24 0.74", "1 1"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              },
            ),
            transformOrigin: "50% 100%",
          }}
        >
          <Oni
            night
            mood="starving"
            size={540}
            look={[
              // Glances at the headline as it lands, then back at you.
              interpolate(
                frame,
                [1.6 * fps, 1.9 * fps, 4.6 * fps, 4.9 * fps],
                [0, -1, -1, 0],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
              ),
              interpolate(frame, [1.6 * fps, 1.9 * fps], [0, 0.4], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            ]}
          />
        </Interactive.Div>

        <Interactive.Div
          name="Hunger tag"
          style={{
            position: "absolute",
            right: 150,
            top: 860,
            fontFamily: mono,
            fontSize: 30,
            letterSpacing: "0.1em",
            background: "#ede6da",
            color: "#2b2724",
            padding: "12px 22px",
            borderRadius: 8,
            rotate: "-4deg",
            opacity: interpolate(frame, [3.2 * fps, 3.3 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(frame, [3.2 * fps, 3.6 * fps], [0.4, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          STARVING · はらぺこ
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Hook = Interactive.create({
  Component: HookInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
