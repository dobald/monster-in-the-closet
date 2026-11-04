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
import { Oni } from "../Oni";
import { display, mono } from "../theme";

// The beats, in seconds: tap "Wear this", the jeans fly to the oni, it bites, swells, celebrates.
const TAP = 1.6;
const FLY = 2.13;
const BITE = 3.23; // on beat 123 of the music
const FULL = 4.53; // on beat 125

// Where things sit on screen.
const ONI = { left: 170, top: 440, size: 420 };
const MOUTH = {
  x: ONI.left + (80 / 160) * ONI.size,
  y: ONI.top + (106 / 176) * ONI.size * (176 / 160),
};
const FROM = { x: 1590, y: 520 };

const CONFETTI = Array.from({ length: 22 }, (_, i) => {
  const a = (i / 22) * Math.PI * 2 + (i % 3) * 0.3;
  return {
    a,
    v: 520 + (i % 5) * 120,
    color: ["#c4472f", "#34506b", "#e9b43c", "#f3eee5"][i % 4],
    spin: (i % 2 ? 1 : -1) * (200 + i * 20),
  };
});

const RescuedInner = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const fly = interpolate(frame, [FLY * fps, BITE * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  const chomp =
    t < BITE
      ? interpolate(frame, [(FLY + 0.3) * fps, (BITE - 0.1) * fps], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : interpolate(frame, [BITE * fps, (BITE + 0.12) * fps], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const fullness = interpolate(
    frame,
    [(BITE + 0.2) * fps, FULL * fps],
    [0.05, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.cubic),
    },
  );
  // Each gulp makes it wobble as the belly fills.
  const gulp =
    t > BITE && t < FULL
      ? Math.sin((t - BITE) * 14) * 0.04 * (1 - (t - BITE) / (FULL - BITE))
      : 0;
  const alive = interpolate(frame, [(BITE + 0.2) * fps, FULL * fps], [44, 67], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const burst = t - FULL;
  return (
    <>
      <Backdrop name="Backdrop" kanji="救出" />
      <Camera hits={[BITE + 0.05, FULL + 0.05]}>
        <Interactive.Div
          name="Oni"
          style={{
            position: "absolute",
            left: ONI.left,
            top: ONI.top,
            scale: `${(1 + gulp).toFixed(3)} ${(1 - gulp).toFixed(3)}`,
            // Anticipation: it leans back as the jeans come, then lunges forward to bite.
            rotate: interpolate(
              frame,
              [
                (FLY + 0.4) * fps,
                (BITE - 0.2) * fps,
                BITE * fps,
                (BITE + 0.3) * fps,
              ],
              ["0deg", "-8deg", "6deg", "0deg"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            transformOrigin: "50% 100%",
          }}
        >
          <Oni
            night
            mood={t < FULL ? "starving" : "fed"}
            fullness={fullness}
            size={ONI.size}
            chomp={chomp}
            look={[
              interpolate(
                frame,
                [FLY * fps, (FLY + 0.3) * fps, (BITE - 0.2) * fps],
                [-0.6, 1, 0],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
              ),
              -0.3,
            ]}
          />
        </Interactive.Div>

        <Interactive.Div
          name="Munch"
          style={{
            position: "absolute",
            left: 640,
            top: 420,
            fontFamily: display,
            fontSize: 64,
            color: "#c4472f",
            rotate: "-10deg",
            opacity: interpolate(
              frame,
              [
                BITE * fps,
                (BITE + 0.05) * fps,
                (BITE + 1.2) * fps,
                (BITE + 1.5) * fps,
              ],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
            scale: interpolate(
              frame,
              [BITE * fps, (BITE + 0.3) * fps],
              [2.2, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                output: "perceptual-scale",
              },
            ),
          }}
        >
          もぐもぐ!
        </Interactive.Div>

        {burst > 0 && burst < 1.6 && (
          <div
            style={{ position: "absolute", left: MOUTH.x, top: MOUTH.y - 60 }}
          >
            {CONFETTI.map((c, i) => (
              <div
                key={i}
                style={{
                  position: "absolute",
                  width: 22,
                  height: 12,
                  background: c.color,
                  border: "2px solid #ede6da",
                  translate: `${Math.cos(c.a) * c.v * burst}px ${Math.sin(c.a) * c.v * burst + 700 * burst * burst}px`,
                  rotate: `${c.spin * burst}deg`,
                  opacity: 1 - burst / 1.6,
                }}
              />
            ))}
          </div>
        )}

        <Interactive.Div
          name="Closet alive meter"
          style={{
            position: "absolute",
            left: 720,
            top: 560,
            width: 520,
            color: "#ede6da",
          }}
        >
          <div
            style={{ fontFamily: mono, fontSize: 28, letterSpacing: "0.1em" }}
          >
            CLOSET ALIVE
          </div>
          <div
            style={{
              fontFamily: display,
              fontSize: 160,
              lineHeight: 1.05,
              color: t >= FULL ? "#d9573d" : "#ede6da",
              scale: String(
                t >= FULL
                  ? interpolate(
                      frame,
                      [FULL * fps, (FULL + 0.3) * fps],
                      [1.25, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                      },
                    )
                  : 1,
              ),
              transformOrigin: "0% 50%",
            }}
          >
            {Math.round(alive)}%
          </div>
          <div
            style={{
              height: 34,
              border: "3px solid #ede6da",
              borderRadius: 17,
              overflow: "hidden",
              background: "#2c2825",
            }}
          >
            <div
              style={{
                width: `${alive}%`,
                height: "100%",
                background: "#ede6da",
              }}
            />
          </div>
          <div
            style={{
              display: "inline-block",
              marginTop: 26,
              fontFamily: mono,
              fontSize: 28,
              letterSpacing: "0.08em",
              background: "#c4472f",
              color: "#ffffff",
              padding: "10px 18px",
              borderRadius: 8,
              rotate: "-2deg",
              scale: String(
                interpolate(
                  frame,
                  [(FULL + 0.4) * fps, (FULL + 0.7) * fps],
                  [0, 1],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
                  },
                ),
              ),
            }}
          >
            JEANS BACK AFTER 400 DAYS
          </div>
        </Interactive.Div>

        <Interactive.Div
          name="Phone"
          style={{ position: "absolute", left: 1370, top: 70 }}
        >
          <Phone
            screens={["10-today", "15-wore-it"]}
            index={interpolate(
              frame,
              [(FULL + 0.2) * fps, (FULL + 0.7) * fps],
              [0, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.7, 0, 0.2, 1),
              },
            )}
            enter={0}
            scale={0.96}
            zoom={interpolate(
              frame,
              [0.3 * fps, 1.1 * fps, (FLY - 0.1) * fps, (FLY + 0.6) * fps],
              [1, 1.5, 1.5, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            )}
            focus={[215, 731]}
            // Only a short way left: the pushed phone has to clear the headline and the meter.
            travel={[-80, -225]}
            spotlight
          >
            <Tap x={215} y={731} at={TAP} />
          </Phone>
        </Interactive.Div>

        {/* After the phone, so its spotlight dims the oni and the meter but not the headline
            that is still being read while the phone is close. */}
        <SceneText
          name="Rescued caption"
          kicker="05 · WEAR IT · 救出成功"
          title="WEAR IT, AND IT EATS."
          body=""
          accent="#c4472f"
          delay={0}
          style={{ position: "absolute", left: 120, top: 80, width: 1150 }}
        />

        {/* The jeans arc from the phone into the oni's mouth, drawn over the phone. */}
        <Img
          src={staticFile("assets/d064b68b32a8366f.png")}
          style={{
            position: "absolute",
            left: FROM.x + (MOUTH.x - FROM.x) * fly - 90,
            top:
              FROM.y +
              (MOUTH.y - FROM.y) * fly -
              Math.sin(fly * Math.PI) * 320 -
              120,
            width: 180,
            height: 240,
            objectFit: "contain",
            rotate: `${fly * 540}deg`,
            scale: String(1.2 - fly * 0.95),
            opacity: t < FLY || t >= BITE ? 0 : 1,
            filter:
              "drop-shadow(0 0 2px #ede6da) drop-shadow(0 0 1px #ede6da) drop-shadow(6px 8px 0 rgba(0, 0, 0, 0.45))",
          }}
        />
      </Camera>
    </>
  );
};

export const Rescued = Interactive.create({
  Component: RescuedInner,
  layout: "absolute-fill",
  schema: { ...Interactive.backgroundSchema },
});
