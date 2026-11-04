import type React from "react";
import {
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C } from "../theme";

// A phone showing app captures. Captures are 860px wide (2x a 430px viewport), so the screen
// scales them to its own width. `scroll` is in capture pixels; full-page captures hide the
// app's fixed tab bar, so pass `tabbar` to lay the real one back over the bottom.
// `screens` with a fractional `index` swipes between captures, like paging in the app.
// `enter` (seconds) tilts the phone in from the side in 3D; it then floats gently.
// `zoom` brings the whole phone toward the camera: it grows around `focus` (the detail that
// matters), travels by `travel` towards the middle of the frame, turns slightly to face you
// and lifts on a deeper shadow. With `spotlight`, the rest of the scene dims while it is close.
export const PHONE_W = 430;
export const PHONE_H = 932;

// The zoom at which a push counts as fully in, for travel, turn, shadow and dimming.
const FULL_PUSH = 1.5;

// Chrome rasterizes a layer with a 3D transform (the perspective, tilt and turn) at its own
// layout size and then stretches it, so a phone laid out at 1x went soft as it zoomed in. The
// 3D layer is laid out at 2x instead (about the captures' own resolution), and a plain 2D scale
// outside it brings it back to size. Measured: as sharp as a flat, untransformed phone; 1.5x
// was not enough and 3x asked for more pixels than the captures have.
const OVERSAMPLE = 2;

export const Phone: React.FC<{
  readonly src?: string;
  readonly screens?: readonly string[];
  readonly index?: number;
  readonly scroll?: number;
  readonly tabbar?: boolean;
  readonly scale?: number;
  readonly enter?: number;
  readonly float?: boolean;
  /** How close the phone comes: 1 is at rest, 1.5 fills most of the frame. */
  readonly zoom?: number;
  /** The detail to come in on, in screen points (the screen is 430 × 932). It stays under the camera. */
  readonly focus?: readonly [number, number];
  /** How far the phone moves at full push, in frame pixels, to bring the focus toward the middle. */
  readonly travel?: readonly [number, number];
  /** Dim everything behind the phone while it is close. */
  readonly spotlight?: boolean;
  readonly style?: React.CSSProperties;
  readonly children?: React.ReactNode;
}> = ({
  src,
  screens,
  index = 0,
  scroll = 0,
  tabbar = false,
  scale = 1,
  enter,
  float = true,
  zoom = 1,
  focus = [PHONE_W / 2, PHONE_H / 2],
  travel = [0, 0],
  spotlight = false,
  style,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const bezel = 14;
  const list = screens ?? (src ? [src] : []);
  const tilt =
    enter === undefined
      ? 0
      : interpolate(frame, [enter * fps, (enter + 1) * fps], [38, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        });
  // 0 at rest, 1 when fully pushed in.
  const push = Math.max(0, Math.min(1, (zoom - 1) / (FULL_PUSH - 1)));
  // The float settles while the phone is close, so the detail holds still under the camera.
  const bob = float ? Math.sin(t * 1.4) * 7 * (1 - push) : 0;
  const lean = float ? Math.sin(t * 0.9) * 0.6 * (1 - push) : 0;
  // The focus point, in this phone's own pixels: the push grows the phone around it.
  const fx = (bezel + focus[0]) * scale;
  const fy = (bezel + focus[1]) * scale;
  const w = (PHONE_W + bezel * 2) * scale;
  const h = (PHONE_H + bezel * 2) * scale;
  return (
    <div
      style={{
        position: "relative",
        width: w,
        height: h,
        flex: "none",
        ...style,
      }}
    >
      {/* A flat 2D shrink back to size, outside the 3D layer (see OVERSAMPLE). */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: w * OVERSAMPLE,
          height: h * OVERSAMPLE,
          transformOrigin: "0 0",
          scale: String(1 / OVERSAMPLE),
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            transformOrigin: `${fx * OVERSAMPLE}px ${fy * OVERSAMPLE}px`,
            // Lengths are in oversampled pixels; angles and the zoom are unchanged.
            transform: [
              `translate(${(travel[0] * push * OVERSAMPLE).toFixed(2)}px, ${(travel[1] * push * OVERSAMPLE).toFixed(2)}px)`,
              `perspective(${1600 * OVERSAMPLE}px)`,
              `translateY(${(bob * OVERSAMPLE).toFixed(2)}px)`,
              `rotateY(${(tilt - 5 * push).toFixed(2)}deg)`,
              `rotateX(${(3 * push).toFixed(2)}deg)`,
              `rotate(${lean.toFixed(2)}deg)`,
              `scale(${zoom.toFixed(4)})`,
            ].join(" "),
          }}
        >
          {spotlight && push > 0 && (
            // Behind the phone only: it dims everything drawn before it in the scene.
            <div
              style={{
                position: "absolute",
                left: -6000 * OVERSAMPLE,
                top: -6000 * OVERSAMPLE,
                width: 12000 * OVERSAMPLE,
                height: 12000 * OVERSAMPLE,
                background: `rgba(20, 18, 16, ${(0.5 * push).toFixed(3)})`,
                pointerEvents: "none",
              }}
            />
          )}
          <PhoneBody
            list={list}
            index={index}
            scroll={scroll}
            tabbar={tabbar}
            push={push}
            scale={scale * OVERSAMPLE}
          >
            {children}
          </PhoneBody>
        </div>
      </div>
    </div>
  );
};

// The phone itself, laid out at 430 × 932 screen points and scaled by `scale`.
const PhoneBody: React.FC<{
  readonly list: readonly string[];
  readonly index: number;
  readonly scroll: number;
  readonly tabbar: boolean;
  readonly push: number;
  readonly scale: number;
  readonly children?: React.ReactNode;
}> = ({ list, index, scroll, tabbar, push, scale, children }) => {
  const bezel = 14;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        width: PHONE_W + bezel * 2,
        height: PHONE_H + bezel * 2,
        transformOrigin: "0 0",
        scale: String(scale),
        borderRadius: 62,
        background: C.sumi,
        // A faint light rim keeps the black bezel from sinking into the dark ground; the
        // soft shadow deepens as the phone comes toward the camera.
        boxShadow: [
          "0 0 0 3px rgba(237, 230, 218, 0.35)",
          `${12 + 10 * push}px ${12 + 16 * push}px 0 #3a3531`,
          `0 ${(40 * push).toFixed(1)}px ${(90 * push).toFixed(1)}px rgba(0, 0, 0, ${(0.55 * push).toFixed(3)})`,
        ].join(", "),
        padding: bezel,
      }}
    >
      <div
        style={{
          position: "relative",
          width: PHONE_W,
          height: PHONE_H,
          borderRadius: 48,
          overflow: "hidden",
          background: C.washi,
        }}
      >
        {list.map((s, i) => (
          <Img
            key={s}
            src={staticFile(`captures/${s}.png`)}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: PHONE_W,
              translate: `${(i - index) * PHONE_W}px ${-scroll / 2}px`,
            }}
          />
        ))}
        {tabbar && (
          <Img
            src={staticFile("captures/tabbar.png")}
            style={{
              position: "absolute",
              left: 0,
              bottom: 0,
              width: PHONE_W,
            }}
          />
        )}
        {children}
      </div>
    </div>
  );
};
