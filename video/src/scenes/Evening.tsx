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
import { Tap } from "../components/Tap";
import { display, mono } from "../theme";

// Night falls: the evening check-in, then the thrift tab, on a neon street.
const EveningInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rise = (at: number) => ({
    opacity: interpolate(frame, [at * fps, (at + 0.15) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    translate: `0px ${interpolate(
      frame,
      [at * fps, (at + 0.6) * fps],
      [600, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.bezier(0.16, 1, 0.3, 1),
      },
    )}px`,
  });
  return (
    <>
      <Backdrop name="Backdrop" kanji="夜" />
      <Camera hits={[5.2]}>
        <Interactive.Div
          name="Check-in phone"
          style={{
            position: "absolute",
            left: 120,
            top: 110,
            rotate: "-2deg",
            ...rise(0),
          }}
        >
          <Phone src="70-checkin" scale={0.84}>
            <Tap x={214} y={234} at={1.8} />
            <Tap x={264} y={311} at={2.6} />
          </Phone>
        </Interactive.Div>
        <Interactive.Div
          name="Check-in caption"
          style={{
            position: "absolute",
            left: 560,
            top: 260,
            width: 420,
            color: "#f3eee5",
            ...rise(0.5),
          }}
        >
          <div
            style={{
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.12em",
              color: "#e9b43c",
            }}
          >
            06 · TONIGHT · 夜
          </div>
          <div
            style={{
              fontFamily: display,
              fontSize: 80,
              lineHeight: 1,
              marginTop: 22,
            }}
          >
            IT ASKS HOW IT WENT.
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Thrift phone"
          style={{
            position: "absolute",
            left: 1000,
            top: 110,
            rotate: "2deg",
            ...rise(3.6),
          }}
        >
          <Phone src="40-thrift-full" tabbar scale={0.84} />
        </Interactive.Div>
        <Interactive.Div
          name="Thrift caption"
          style={{
            position: "absolute",
            left: 1430,
            top: 260,
            width: 350,
            color: "#f3eee5",
            ...rise(4),
          }}
        >
          <div
            style={{
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.12em",
              color: "#e8a08f",
              whiteSpace: "nowrap",
            }}
          >
            07 · THRIFT · 古着
          </div>
          <div
            style={{
              fontFamily: display,
              fontSize: 80,
              lineHeight: 1,
              marginTop: 22,
            }}
          >
            SHOP LAST.
          </div>
          {/* What the Thrift tab promises: second-hand only, never a fast-fashion brand. */}
          <div
            style={{
              display: "inline-block",
              marginTop: 24,
              fontFamily: mono,
              fontSize: 28,
              lineHeight: 1.3,
              letterSpacing: "0.08em",
              background: "#e9b43c",
              color: "#2b2724",
              border: "3px solid #ede6da",
              padding: "8px 16px",
              borderRadius: 8,
              rotate: "2deg",
              transformOrigin: "0% 50%",
              scale: String(
                interpolate(frame, [5.6 * fps, 5.9 * fps], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                }),
              ),
            }}
          >
            SECOND-HAND ONLY
            <br />
            NO FAST FASHION
          </div>
        </Interactive.Div>
        <Interactive.Div
          name="Outfits sticker"
          style={{
            position: "absolute",
            // Slapped over the thrift phone's edge, so it stays inside the side margin.
            left: 1290,
            top: 660,
            fontFamily: display,
            fontSize: 64,
            lineHeight: 1,
            background: "#c4472f",
            color: "#ffffff",
            border: "4px solid #f3eee5",
            padding: "18px 24px",
            borderRadius: 12,
            rotate: "-4deg",
            opacity: interpolate(frame, [5 * fps, 5.1 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(frame, [5 * fps, 5.4 * fps], [2.2, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.34, 1.56, 0.64, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          +15
          <div
            style={{
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.1em",
              marginTop: 6,
            }}
          >
            OUTFITS, ONE PIECE
          </div>
        </Interactive.Div>
      </Camera>
    </>
  );
};

export const Evening = Interactive.create({
  Component: EveningInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
