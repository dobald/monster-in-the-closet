import { useId } from "react";
import type { Mood } from "./api";

// The oni: a closet monster that eats when your clothes get worn and starves when they don't.
// Drawn like a riso print: a red body over an off-register indigo layer, halftone shading, a
// tiger-stripe loincloth. Its body is the closet: `fullness` (the closet-alive share) pinches the
// waist when it's starving and rounds the belly when it's fed.
// Motion per mood: starving trembles and growls, restless shakes, calm breathes, proud floats,
// fed bounces, sleepy dozes.

const MOTION: Record<Mood, string> = {
  starving: "shake 0.5s ease-in-out 0.4s 2, shake 0.5s ease-in-out 3.4s 2",
  restless: "shake 0.6s ease-in-out 0s 2, shake 0.6s ease-in-out 4s 2",
  calm: "breathe 3.2s ease-in-out infinite",
  proud: "float 3s ease-in-out infinite",
  fed: "bounce 1.4s ease-in-out 0.3s 3",
  sleepy: "doze 3.6s ease-in-out infinite",
};

export const MOOD_LABEL: Record<Mood, { en: string; ja: string; line: string }> = {
  starving: { en: "Starving", ja: "はらぺこ", line: "Most of your clothes haven't been out in a month. I live on what you wear. Feed me." },
  restless: { en: "Restless", ja: "そわそわ", line: "Lots of your clothes haven't been out in a while. Let's fix that." },
  calm: { en: "Peckish", ja: "こばら", line: "I could eat. Wear something you've forgotten and I'm happy." },
  proud: { en: "Full", ja: "まんぷく", line: "You're wearing most of what you own. I'm full and showing off." },
  fed: { en: "Fed", ja: "満腹", line: "You rescued something today. Full and happy." },
  sleepy: { en: "Sleepy", ja: "おやすみ", line: "Tell me how today went, then I'll sleep on tomorrow's pick." },
};

const FULLNESS: Record<Mood, number> = { starving: 0.05, restless: 0.3, calm: 0.5, proud: 0.85, fed: 1, sleepy: 0.5 };

const INK = "#2B2724";
const RED = "#C4472F";
const BELLY = "#DB6B4F";
const PAPER = "#F3EEE5";
const TIGER = "#E9B43C";
const BLUSH = "#E8A08F";

const W = 160;
const H = 176;
const CX = 80;

// The body outline: shoulders fixed, belly from gaunt (starving) to round (fed).
function bodyPath(f: number): string {
  const sh = 47 + 7 * f;
  const belly = 36 + 28 * f;
  const waist = belly - 8 * (1 - f); // a starving oni's waist pinches in
  const r = (d: number) => CX + d;
  const l = (d: number) => CX - d;
  // Down the right side from the crown, then back up the left (each curve reversed).
  return [
    `M ${CX} 34`,
    `C ${r(40)} 34 ${r(sh)} 40 ${r(sh)} 68`,
    `C ${r(sh)} 86 ${r(waist)} 98 ${r(belly)} 120`,
    `C ${r(belly)} 142 ${r(belly - 16)} 152 ${CX} 152`,
    `C ${l(belly - 16)} 152 ${l(belly)} 142 ${l(belly)} 120`,
    `C ${l(waist)} 98 ${l(sh)} 86 ${l(sh)} 68`,
    `C ${l(sh)} 40 ${l(40)} 34 ${CX} 34 Z`,
  ].join(" ");
}

type Arm = { shoulder: [number, number]; hand: [number, number] };

function arms(mood: Mood, f: number): Arm[] {
  const sh = 43 + 7 * f;
  const belly = 36 + 28 * f;
  const pose = (dx: number, dy: number, hx: number, hy: number): Arm[] => [
    { shoulder: [CX - dx, dy], hand: [CX - hx, hy] },
    { shoulder: [CX + dx, dy], hand: [CX + hx, hy] },
  ];
  switch (mood) {
    case "starving":
      return pose(sh - 4, 98, 20, 124); // clutching its empty belly
    case "fed":
      return pose(sh - 2, 70, sh + 18, 40); // arms up
    case "proud":
      return pose(sh - 2, 72, belly - 4, 116); // hands on hips
    case "sleepy":
      return pose(sh - 2, 76, sh - 4, 116);
    default:
      return pose(sh - 2, 74, sh + 6, 110);
  }
}

export default function Oni({ mood, size = 64, night = false, fullness }: { mood: Mood; size?: number; night?: boolean; fullness?: number }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const f = Math.max(0, Math.min(1, fullness ?? FULLNESS[mood]));
  const body = bodyPath(f);
  // The outer edge follows the theme's ink (light in dark mode) so the silhouette never disappears.
  const edge = night ? PAPER : "var(--sumi)";
  const detail = size >= 44; // halftone and stripes muddy a tiny icon
  return (
    <span
      role="img"
      aria-label={`Oni, feeling ${MOOD_LABEL[mood].en.toLowerCase()}`}
      style={{ position: "relative", display: "inline-block", width: size, height: size * (H / W), flex: "none" }}
    >
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ overflow: "visible", animation: MOTION[mood] }}>
        <defs>
          <clipPath id={`b${uid}`}>
            <path d={body} />
          </clipPath>
          <pattern id={`h${uid}`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
            <circle cx="2.5" cy="2.5" r="1.15" fill={INK} />
          </pattern>
        </defs>

        {/* off-register indigo print layer */}
        <path d={body} transform="translate(5 4)" fill="var(--ai)" opacity="0.9" />

        {/* feet */}
        {[-16, 16].map((dx) => (
          <ellipse key={dx} cx={CX + dx} cy={156} rx={13} ry={7} fill={RED} stroke={edge} strokeWidth="1.5" />
        ))}

        {/* horns: curved, banded */}
        <path d="M58 46 C50 30 48 16 58 2 C62 16 66 30 72 42 Z" fill={PAPER} stroke={edge} strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M102 46 C110 30 112 16 102 2 C98 16 94 30 88 42 Z" fill={PAPER} stroke={edge} strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M55 28 L64 25 M53 18 L60 15 M105 28 L96 25 M107 18 L100 15" stroke={INK} strokeWidth="1.3" strokeLinecap="round" />

        {/* body */}
        <path d={body} fill={RED} />
        <g clipPath={`url(#b${uid})`}>
          <ellipse cx={CX} cy={114} rx={20 + 12 * f} ry={17 + 7 * f} fill={BELLY} />
          {detail && <rect x={CX + 18} y="20" width="80" height="140" fill={`url(#h${uid})`} opacity="0.22" />}
          <ellipse cx={CX - 26} cy={52} rx={12} ry={7} fill="#fff" opacity="0.22" transform={`rotate(-30 ${CX - 26} 52)`} />
          {/* tiger-stripe loincloth */}
          <rect x="0" y="132" width={W} height="24" fill={TIGER} />
          {detail && (
            <path
              d="M18 132 l6 10 l-4 0 l6 12 M40 132 l5 12 l-3 0 l5 10 M62 132 l4 9 l-3 0 l5 13 M86 132 l5 11 l-3 0 l4 11 M108 132 l5 10 l-3 0 l5 12 M130 132 l5 12 l-3 0 l5 10"
              fill="none"
              stroke={INK}
              strokeWidth="3"
              strokeLinejoin="round"
            />
          )}
          <path d={`M0 132 H${W}`} stroke={INK} strokeWidth="1.5" />
          {f < 0.3 && detail && (
            // ribs: it's been living on nothing
            <path d="M50 96 q8 -4 14 0 M48 104 q8 -4 15 0 M50 112 q7 -3 12 0 M110 96 q-8 -4 -14 0 M112 104 q-8 -4 -15 0 M110 112 q-7 -3 -12 0" fill="none" stroke={INK} strokeWidth="1.6" strokeLinecap="round" opacity="0.55" />
          )}
        </g>
        <path d={body} fill="none" stroke={edge} strokeWidth="1.8" />

        {/* hair tuft between the horns */}
        <path d="M66 40 q3 -12 9 -4 q3 -11 10 -1 q4 -10 9 4 q-14 6 -28 1 Z" fill={INK} />

        {mood === "proud" && (
          <g>
            <path d={`M${CX - 52} 52 Q${CX} 44 ${CX + 52} 52 L${CX + 53} 62 Q${CX} 54 ${CX - 53} 62 Z`} fill={PAPER} stroke={INK} strokeWidth="1.5" />
            <circle cx={CX} cy={53} r="4.5" fill={RED} />
          </g>
        )}

        {/* arms: body-red capsules with an ink edge, then a hand */}
        {arms(mood, f).map((a, i) => (
          <g key={i}>
            <line x1={a.shoulder[0]} y1={a.shoulder[1]} x2={a.hand[0]} y2={a.hand[1]} stroke={edge} strokeWidth="14" strokeLinecap="round" />
            <line x1={a.shoulder[0]} y1={a.shoulder[1]} x2={a.hand[0]} y2={a.hand[1]} stroke={RED} strokeWidth="10.5" strokeLinecap="round" />
            <circle cx={a.hand[0]} cy={a.hand[1]} r="7" fill={RED} stroke={edge} strokeWidth="1.5" />
          </g>
        ))}

        <Face mood={mood} />
      </svg>

      {mood === "starving" && size >= 44 && (
        <span
          aria-hidden="true"
          lang="ja"
          style={{
            position: "absolute",
            right: -size * 0.16,
            top: size * 0.52,
            fontFamily: "var(--display)",
            fontSize: Math.max(10, size * 0.14),
            color: night ? PAPER : "var(--sumi)",
            transform: "rotate(-12deg)",
            animation: "growl 2.4s ease-in-out infinite",
          }}
        >
          ぐぅ
        </span>
      )}
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
  const cheeks = (
    <g fill={BLUSH} opacity="0.8">
      <ellipse cx="54" cy="96" rx="8" ry="4" />
      <ellipse cx="106" cy="96" rx="8" ry="4" />
    </g>
  );
  // Two small tusks pointing up from the lower lip.
  const tusks = (y: number) => (
    <path d={`M68 ${y} l3 -7 l3 7 Z M86 ${y} l3 -7 l3 7 Z`} fill={PAPER} stroke={INK} strokeWidth="1" strokeLinejoin="round" />
  );
  const brow = (d: string) => <path d={d} fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />;
  switch (mood) {
    case "starving":
      return (
        <g>
          {brow("M52 66 L66 60 M108 66 L94 60")}
          <circle cx="62" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="98" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="62" cy="85" r="3.2" fill={INK} />
          <circle cx="98" cy="85" r="3.2" fill={INK} />
          <path d="M64 100 q4 -5 8 0 t8 0 t8 0 t8 0 V108 a16 10 0 0 1 -32 0 Z" fill={INK} />
          <path d="M86 108 q2 8 0 12 q-3 -2 -2 -6" fill="#8FB3D9" stroke={INK} strokeWidth="1" />
          <path d="M120 48 q6 10 0 14 q-6 -4 0 -14 Z" fill="#8FB3D9" stroke={INK} strokeWidth="1.2" />
        </g>
      );
    case "fed":
      return (
        <g>
          {brow("M50 66 q10 -6 20 0 M90 66 q10 -6 20 0")}
          <path d="M52 82 a10 10 0 0 1 20 0 M88 82 a10 10 0 0 1 20 0" fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />
          {cheeks}
          <path d="M60 98 h40 v4 a20 18 0 0 1 -40 0 Z" fill={INK} />
          <path d="M70 114 a10 7 0 0 1 20 0 Z" fill={BLUSH} />
          {tusks(99)}
          <path d="M28 40 l3 6 l6 1 l-5 4 l1 6 l-5 -3 l-5 3 l1 -6 l-5 -4 l6 -1 Z M136 34 l2 4 l4 1 l-3 3 l1 4 l-4 -2 l-4 2 l1 -4 l-3 -3 l4 -1 Z" fill={TIGER} stroke={INK} strokeWidth="1" />
        </g>
      );
    case "proud":
      return (
        <g>
          {brow("M50 70 l18 -3 M110 70 l-18 -3")}
          <path d="M52 84 a10 8 0 0 1 20 0 M88 84 a10 8 0 0 1 20 0" fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />
          {cheeks}
          <path d="M62 100 q18 14 36 0" fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />
          {tusks(104)}
        </g>
      );
    case "sleepy":
      return (
        <g>
          <path d="M52 82 a10 7 0 0 0 20 0 M88 82 a10 7 0 0 0 20 0" fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />
          {cheeks}
          <ellipse cx="80" cy="104" rx="7" ry="5.5" fill={INK} />
        </g>
      );
    case "restless":
      return (
        <g>
          {brow("M52 64 L68 68 M108 64 L92 68")}
          <circle cx="62" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="98" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="66" cy="78" r="5" fill={INK} />
          <circle cx="102" cy="78" r="5" fill={INK} />
          <path d="M60 104 q5 -6 10 0 t10 0 t10 0 t10 0" fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round" />
          <path d="M122 48 q6 10 0 14 q-6 -4 0 -14 Z" fill="#8FB3D9" stroke={INK} strokeWidth="1.2" />
        </g>
      );
    default:
      return (
        <g>
          {brow("M52 66 h16 M92 66 h16")}
          <circle cx="62" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="98" cy="80" r="11" fill="#fff" stroke={INK} strokeWidth="1.5" />
          <circle cx="64" cy="82" r="5" fill={INK} />
          <circle cx="96" cy="82" r="5" fill={INK} />
          {cheeks}
          <path d="M64 100 h32 v3 a10 10 0 0 1 -10 9 h-12 a10 10 0 0 1 -10 -9 Z" fill={INK} />
          {tusks(101)}
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
        color: night ? PAPER : "var(--sumi)",
        animation: `zzz 2.6s ease-out ${delay}s infinite`,
      }}
    >
      z
    </span>
  );
}
