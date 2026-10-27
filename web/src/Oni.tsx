import type { Mood } from "./api";

// The oni mascot, one SVG with a face per mood (wireframe "Oni mood states").
// Motion per mood: restless shakes, calm breathes, proud floats, fed bounces, sleepy dozes.

const MOTION: Record<Mood, string> = {
  restless: "shake 0.6s ease-in-out 0s 2, shake 0.6s ease-in-out 4s 2",
  calm: "breathe 3.2s ease-in-out infinite",
  proud: "float 3s ease-in-out infinite",
  fed: "bounce 1.4s ease-in-out 0.3s 3",
  sleepy: "doze 3.6s ease-in-out infinite",
};

export const MOOD_LABEL: Record<Mood, { en: string; ja: string; line: string }> = {
  restless: { en: "Restless", ja: "そわそわ", line: "Lots of your clothes haven't been out in a while. Let's fix that." },
  calm: { en: "Calm", ja: "のんびり", line: "Your closet is in good shape. I've got today covered." },
  proud: { en: "Proud", ja: "ドヤ", line: "You're wearing most of what you own. Showing off a little." },
  fed: { en: "Fed", ja: "満腹", line: "You rescued something today. Full and happy." },
  sleepy: { en: "Sleepy", ja: "おやすみ", line: "Tell me how today went, then I'll sleep on tomorrow's pick." },
};

export default function Oni({ mood, size = 64, night = false }: { mood: Mood; size?: number; night?: boolean }) {
  const ink = "#2B2724";
  const horn = night ? "#F3EEE5" : ink;
  return (
    <span
      role="img"
      aria-label={`Oni, feeling ${MOOD_LABEL[mood].en.toLowerCase()}`}
      style={{ position: "relative", display: "inline-block", width: size, height: size * (150 / 140), flex: "none" }}
    >
      <svg viewBox="0 0 140 150" width="100%" height="100%" style={{ overflow: "visible", animation: MOTION[mood] }}>
        <path d="M26 30 38 0 50 30Z M90 30 102 0 114 30Z" fill={horn} />
        <rect x="1" y="23" width="138" height="126" rx="30" fill="#C4472F" stroke={ink} strokeWidth="1.5" />
        {mood === "proud" && (
          <g>
            <rect x="1" y="40" width="138" height="16" fill="#F3EEE5" stroke={ink} strokeWidth="1.5" />
            <circle cx="70" cy="48" r="5" fill="#C4472F" />
          </g>
        )}
        <Face mood={mood} />
      </svg>
      {mood === "sleepy" && (
        <>
          <Z right={-6} top={6} size={size * 0.16} delay={0} night={night} />
          <Z right={-14} top={0} size={size * 0.12} delay={1.3} night={night} />
        </>
      )}
    </span>
  );
}

function Face({ mood }: { mood: Mood }) {
  const ink = "#2B2724";
  const cheeks = (
    <g fill="#F3EEE5" opacity="0.5">
      <ellipse cx="27" cy="92" rx="9" ry="4.5" />
      <ellipse cx="113" cy="92" rx="9" ry="4.5" />
    </g>
  );
  switch (mood) {
    case "fed":
      return (
        <g>
          <path d="M28 76a12 12 0 0 1 24 0M88 76a12 12 0 0 1 24 0" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          {cheeks}
          <path d="M50 96h40v6a20 20 0 0 1-40 0Z" fill={ink} />
          <path d="M60 116a10 8 0 0 1 20 0Z" fill="#E8A08F" />
        </g>
      );
    case "proud":
      return (
        <g>
          <path d="M28 80a12 10 0 0 1 24 0M88 80a12 10 0 0 1 24 0" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          {cheeks}
          <path d="M52 102q18 14 36 0" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
        </g>
      );
    case "sleepy":
      return (
        <g>
          <path d="M28 76a12 8 0 0 0 24 0M88 76a12 8 0 0 0 24 0" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          <ellipse cx="70" cy="106" rx="8" ry="6" fill={ink} />
        </g>
      );
    case "restless":
      return (
        <g>
          <circle cx="40" cy="74" r="12" fill="#fff" />
          <circle cx="100" cy="74" r="12" fill="#fff" />
          <circle cx="45" cy="72" r="5.5" fill={ink} />
          <circle cx="105" cy="72" r="5.5" fill={ink} />
          <path d="M50 108q5-6 10 0t10 0 10 0 10 0" fill="none" stroke={ink} strokeWidth="4" strokeLinecap="round" />
          <path d="M124 46q6 10 0 14q-6-4 0-14Z" fill="#8FB3D9" stroke={ink} strokeWidth="1.2" />
        </g>
      );
    default:
      return (
        <g>
          <circle cx="40" cy="74" r="12" fill="#fff" />
          <circle cx="100" cy="74" r="12" fill="#fff" />
          <circle cx="42" cy="77" r="5.5" fill={ink} />
          <circle cx="98" cy="77" r="5.5" fill={ink} />
          <path d="M54 104h32v3a8 8 0 0 1-8 8H62a8 8 0 0 1-8-8Z" fill={ink} />
        </g>
      );
  }
}

function Z({ right, top, size, delay, night }: { right: number; top: number; size: number; delay: number; night: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        right,
        top,
        fontFamily: "var(--display)",
        fontSize: Math.max(10, size),
        color: night ? "#F3EEE5" : "#2B2724",
        animation: `zzz 2.6s ease-out ${delay}s infinite`,
      }}
    >
      z
    </span>
  );
}
