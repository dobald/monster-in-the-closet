import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";
import { AbsoluteFill, Easing } from "remotion";

// A cut that grows out of the shot's subject: the next scene opens in a circle from (x, y),
// percent of the frame, led by an ink ring. Motion carries across the cut instead of a fade.
type IrisProps = { x: number; y: number; color: string };

const RADIUS = 2300; // px: enough to clear the far corner of a 1920 × 1080 frame from anywhere
const RING = 16;

const Iris = ({
  children,
  presentationDirection,
  presentationProgress,
  passedProps,
}: TransitionPresentationComponentProps<IrisProps>) => {
  if (presentationDirection === "exiting") {
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }
  // Snap curve (STYLE.md): starts slow, opens fast, lands softly.
  const p = Easing.bezier(0.7, 0, 0.2, 1)(presentationProgress);
  const r = p * RADIUS;
  const { x, y, color } = passedProps;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ clipPath: `circle(${r}px at ${x}% ${y}%)` }}>
        {children}
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: `${x}%`,
          top: `${y}%`,
          width: r * 2 + RING * 2,
          height: r * 2 + RING * 2,
          translate: "-50% -50%",
          borderRadius: "50%",
          border: `${RING}px solid ${color}`,
          opacity: 1 - p * p,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

export const iris = (props: IrisProps): TransitionPresentation<IrisProps> => ({
  component: Iris,
  props,
});
