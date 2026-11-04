import type React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

// A scene's camera: a slow push-in over the whole scene, plus a short decaying shake after
// each `hits` time (in seconds), for stamps landing and other impacts. The street background
// sits outside the camera, so the push-in also reads as depth against it.
export const Camera: React.FC<{
  readonly hits?: readonly number[];
  readonly push?: number;
  readonly children: React.ReactNode;
}> = ({ hits = [], push = 0.035, children }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  let dx = 0;
  let dy = 0;
  for (const h of hits) {
    const since = t - h;
    if (since < 0 || since > 0.4) continue;
    const decay = 1 - since / 0.4;
    dx += Math.sin(since * 90) * 14 * decay;
    dy += Math.cos(since * 70) * 9 * decay;
  }
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        scale: String(1 + push * (frame / durationInFrames)),
        translate: `${dx.toFixed(2)}px ${dy.toFixed(2)}px`,
      }}
    >
      {children}
    </div>
  );
};
