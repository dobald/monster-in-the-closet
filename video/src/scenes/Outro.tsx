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

const TITLE = ["MONSTER", "IN THE", "CLOSET"];

const OutroInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Backdrop name="Backdrop" kanji="鬼" />
      <Camera hits={[1.35]}>
        <Interactive.Div
          name="Oni"
          style={{
            position: "absolute",
            left: 200,
            top: 260,
            // Pops up from the bottom with a springy overshoot, then floats and waves.
            translate: interpolate(
              frame,
              [0, 0.7 * fps],
              ["0px 900px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              },
            ),
          }}
        >
          <Oni
            mood="proud"
            size={440}
            night
            wave={frame > 1.6 * fps}
            look={[0.4, 0]}
          />
        </Interactive.Div>

        <Interactive.Div
          name="Outro title"
          style={{
            position: "absolute",
            left: 780,
            top: 240,
            width: 1020,
            fontFamily: display,
            fontSize: 132,
            lineHeight: 0.92,
            color: "#f3eee5",
          }}
        >
          {TITLE.map((line, i) => {
            const at = (0.5 + i * 0.28) * fps;
            return (
              <div
                key={line}
                style={{
                  opacity: interpolate(frame, [at, at + 0.08 * fps], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                  scale: String(
                    interpolate(frame, [at, at + 0.3 * fps], [2, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    }),
                  ),
                  transformOrigin: "0% 50%",
                }}
              >
                {line}
              </div>
            );
          })}
        </Interactive.Div>
        <Interactive.Div
          name="Outro tagline"
          style={{
            position: "absolute",
            left: 780,
            top: 640,
            fontFamily: body,
            fontWeight: 700,
            fontSize: 48,
            color: "#e8a08f",
            opacity: interpolate(frame, [1.8 * fps, 2.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Wear what you already own. Keep the monster fed.
        </Interactive.Div>
        <Interactive.Div
          name="Outro credit"
          style={{
            position: "absolute",
            left: 780,
            top: 760,
            fontFamily: mono,
            fontSize: 28,
            letterSpacing: "0.1em",
            color: "#cfc7ba",
            opacity: interpolate(frame, [2.4 * fps, 2.8 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          META GLOBAL AI DEVELOPER HACKATHON · INDIE TRACK
        </Interactive.Div>
        {/* Required by the music's Creative Commons license: the generator's wording, unchanged. */}
        <Interactive.Div
          name="Music credit"
          style={{
            position: "absolute",
            left: 780,
            top: 840,
            width: 1020,
            fontFamily: body,
            fontSize: 28,
            lineHeight: 1.35,
            color: "#a39a8e",
            opacity: interpolate(frame, [2.8 * fps, 3.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Music: “Local Forecast” Kevin MacLeod (incompetech.com)
          <br />
          Licensed under Creative Commons: By Attribution 4.0
          <br />
          http://creativecommons.org/licenses/by/4.0/
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Outro = Interactive.create({
  Component: OutroInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
