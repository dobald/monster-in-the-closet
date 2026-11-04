import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import { display } from "../theme";

// A scene change through a noren curtain: five panels drop in one after another to cover the
// frame, the scenes swap behind them, and the panels lift away again.
const PANELS = [
  { color: "#c4472f", text: "" },
  { color: "#34506b", text: "服" },
  { color: "#2b2724", text: "鬼" },
  { color: "#34506b", text: "選" },
  { color: "#c4472f", text: "" },
];

const Noren = ({
  children,
  presentationDirection,
  presentationProgress,
}: TransitionPresentationComponentProps<Record<string, never>>) => {
  const p = presentationProgress;
  if (presentationDirection === "exiting") {
    return (
      <AbsoluteFill style={{ opacity: p < 0.5 ? 1 : 0 }}>
        {children}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: p >= 0.5 ? 1 : 0 }}>
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        {PANELS.map((panel, i) => {
          const lag = i * 0.05;
          const down = interpolate(p, [lag, 0.42 + lag * 0.3], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          });
          const up = interpolate(p, [0.58 + lag * 0.3, 0.95], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.in(Easing.cubic),
          });
          const y = (down - 1) * 105 - up * 105;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                top: 0,
                left: `${i * 20}%`,
                width: "20.4%",
                height: "100%",
                translate: `0px ${y}%`,
                background: panel.color,
                borderLeft: "4px solid #f3eee5",
                transformOrigin: "50% 0%",
                transform: `skewX(${Math.sin(p * Math.PI * 2 + i) * 3}deg)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: display,
                fontSize: 180,
                color: "#f3eee5",
              }}
            >
              {panel.text}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const noren = (): TransitionPresentation<Record<string, never>> => ({
  component: Noren,
  props: {},
});
