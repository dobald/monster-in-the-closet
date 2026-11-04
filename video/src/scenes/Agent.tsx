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
import { mono } from "../theme";

// The steps shown in the app's "How the oni decided" trace, in order.
const CALLS = [
  "get_weather()",
  "get_calendar()",
  "stretch()",
  "score()",
  "taste_model()",
  "CHECK · PASSED",
];
const STEP = 0.4; // seconds between calls

const AgentInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const first = 1.5;
  return (
    <>
      <Backdrop name="Backdrop" kanji="判断" />
      <Camera hits={[first + (CALLS.length - 1) * STEP]}>
        <SceneText
          name="Agent caption"
          kicker="04 · IT SHOWS ITS WORK · 判断"
          title="EVERY PICK IS CHECKED AGAINST YOUR REAL CLOSET."
          body=""
          accent="#6a8db2"
          delay={0.1}
          style={{ position: "absolute", left: 120, top: 100, width: 1060 }}
        />

        <Interactive.Div
          name="Tool calls"
          style={{
            position: "absolute",
            left: 120,
            top: 700,
            width: 1100,
            display: "flex",
            flexWrap: "wrap",
            gap: 20,
          }}
        >
          {CALLS.map((call, i) => {
            const at = (first + i * STEP) * fps;
            const last = i === CALLS.length - 1;
            return (
              <span
                key={call}
                style={{
                  fontFamily: mono,
                  fontSize: 34,
                  padding: "12px 20px",
                  border: "3px solid #ede6da",
                  borderRadius: 12,
                  background: last ? "#c4472f" : "#2c2825",
                  color: last ? "#ffffff" : "#ede6da",
                  boxShadow: "5px 5px 0 #ede6da",
                  rotate: `${(i % 3) - 1}deg`,
                  opacity: interpolate(frame, [at, at + 0.06 * fps], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                  scale: String(
                    interpolate(
                      frame,
                      [at, at + 0.3 * fps],
                      [last ? 2 : 0.3, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.bezier(0.16, 1, 0.3, 1),
                      },
                    ),
                  ),
                }}
              >
                {call}
              </span>
            );
          })}
        </Interactive.Div>

        <Interactive.Div
          name="Phone"
          style={{ position: "absolute", left: 1370, top: 70 }}
        >
          <Phone src="14-trace" enter={0} scale={0.96}>
            {/* A reading highlight runs down the trace in step with the calls. */}
            <div
              style={{
                position: "absolute",
                left: 8,
                right: 8,
                height: 70,
                borderRadius: 10,
                background: "rgba(52, 80, 107, 0.16)",
                border: "2px solid rgba(52, 80, 107, 0.5)",
                top: interpolate(
                  frame,
                  [
                    first * fps,
                    (first + (CALLS.length - 1) * STEP + 0.4) * fps,
                  ],
                  [290, 860],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  },
                ),
                opacity: interpolate(
                  frame,
                  [(first - 0.2) * fps, first * fps, 4.4 * fps, 4.8 * fps],
                  [0, 1, 1, 0],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                ),
              }}
            />
          </Phone>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Agent = Interactive.create({
  Component: AgentInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
