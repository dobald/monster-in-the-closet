import type React from "react";
import { useId } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { display } from "./theme";

// The app's oni (web/src/Oni.tsx), redrawn frame by frame: the same riso-print body, whose
// `fullness` pinches the waist when starving and rounds the belly when fed. The app's CSS
// keyframes don't render in a video, so motion() replays them from the frame time, with extra
// character on top: squash and stretch, blinks, eyes that look somewhere, a wave and a chomp.
export type Mood =
  | "starving"
  | "restless"
  | "calm"
  | "proud"
  | "fed"
  | "sleepy";

const squash = (sy: number): React.CSSProperties => ({
  scale: `${(2 - sy).toFixed(3)} ${sy.toFixed(3)}`,
  transformOrigin: "50% 92%",
});

function motion(mood: Mood, t: number): React.CSSProperties {
  const breathe = 1 + 0.02 * Math.sin(t * 2.2);
  switch (mood) {
    case "starving":
    case "restless":
      // A tremble every few seconds, like the app's two-shake loop, over a weak breath.
      return {
        ...squash(breathe),
        translate: `${(t % 3 < 1 ? Math.sin(t * 40) * 3 * Math.sin((t % 3) * Math.PI) : 0).toFixed(2)}px 0px`,
      };
    case "calm":
      return squash(1 + 0.03 * Math.sin((t / 3.2) * Math.PI * 2));
    case "proud":
      return {
        ...squash(breathe),
        translate: `0px ${(-6 * Math.sin((t / 3) * Math.PI * 2)).toFixed(2)}px`,
      };
    case "fed": {
      // Hops: up on a sine, squashed flat for a moment each time it lands.
      const h = Math.sin(((t / 0.75) % 1) * Math.PI);
      return {
        ...squash(1 - 0.12 * Math.pow(1 - h, 8) + 0.05 * h),
        translate: `0px ${(-26 * h).toFixed(2)}px`,
      };
    }
    case "sleepy":
      return {
        rotate: `${(3 * Math.sin((t / 3.6) * Math.PI * 2)).toFixed(2)}deg`,
        transformOrigin: "50% 100%",
      };
  }
}

// 0 = open, 1 = shut: a quick blink every few seconds.
function lidAt(t: number): number {
  const p = (t + 0.7) % 3.6;
  return p < 0.16 ? Math.sin((p / 0.16) * Math.PI) : 0;
}

const FULLNESS: Record<Mood, number> = {
  starving: 0.05,
  restless: 0.3,
  calm: 0.5,
  proud: 0.85,
  fed: 1,
  sleepy: 0.5,
};

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

function arms(mood: Mood, f: number, wave: boolean, t: number): Arm[] {
  const sh = 43 + 7 * f;
  const belly = 36 + 28 * f;
  const pose = (dx: number, dy: number, hx: number, hy: number): Arm[] => [
    { shoulder: [CX - dx, dy], hand: [CX - hx, hy] },
    { shoulder: [CX + dx, dy], hand: [CX + hx, hy] },
  ];
  if (wave) {
    // The left arm keeps the mood's pose; the right one swings above the shoulder.
    const [left] = arms(mood, f, false, t);
    const shoulder: [number, number] = [CX + sh - 2, 72];
    const a = ((-62 + 24 * Math.sin(t * 9)) * Math.PI) / 180;
    return [
      left,
      {
        shoulder,
        hand: [shoulder[0] + 40 * Math.cos(a), shoulder[1] + 40 * Math.sin(a)],
      },
    ];
  }
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

export function Oni({
  mood,
  size = 64,
  night = false,
  fullness,
  look = [0, 0],
  wave = false,
  chomp = 0,
}: {
  readonly mood: Mood;
  readonly size?: number;
  readonly night?: boolean;
  readonly fullness?: number;
  /** Where the pupils point, each from -1 to 1. */
  readonly look?: readonly [number, number];
  readonly wave?: boolean;
  /** How wide the mouth is open for a bite, 0 to 1. */
  readonly chomp?: number;
}) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // The oni acts on twos (STYLE.md): its own motion steps every 2 frames, like hand-drawn
  // animation, while the camera and the scene around it stay smooth.
  const twos = Math.floor(frame / 2) * 2;
  const t = twos / fps;
  // Line boil: three seeded wobble variants, changing every 2 frames, never strobing.
  const boilSeed = [3, 11, 23][Math.floor(frame / 2) % 3];
  const f = Math.max(0, Math.min(1, fullness ?? FULLNESS[mood]));
  const body = bodyPath(f);
  // The outer edge follows the theme's ink (light in dark mode) so the silhouette never disappears.
  const edge = night ? PAPER : INK;
  const detail = size >= 44; // halftone and stripes muddy a tiny icon
  return (
    <span
      role="img"
      aria-label={`Oni, feeling ${mood}`}
      style={{
        position: "relative",
        display: "inline-block",
        width: size,
        height: size * (H / W),
        flex: "none",
      }}
    >
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height="100%"
        style={{ overflow: "visible", ...motion(mood, t) }}
      >
        <defs>
          <clipPath id={`b${uid}`}>
            <path d={body} />
          </clipPath>
          <pattern
            id={`h${uid}`}
            width="5"
            height="5"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(30)"
          >
            <circle cx="2.5" cy="2.5" r="1.15" fill={INK} />
          </pattern>
          <filter
            id={`boil${uid}`}
            x="-10%"
            y="-10%"
            width="120%"
            height="120%"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.045"
              numOctaves="2"
              seed={boilSeed}
              result="noise"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale={detail ? 2.4 : 0}
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>
        </defs>
        <g filter={`url(#boil${uid})`}>
          {/* off-register indigo print layer */}
          <path
            d={body}
            transform="translate(5 4)"
            fill="#34506B"
            opacity="0.9"
          />

          {/* feet */}
          {[-16, 16].map((dx) => (
            <ellipse
              key={dx}
              cx={CX + dx}
              cy={156}
              rx={13}
              ry={7}
              fill={RED}
              stroke={edge}
              strokeWidth="1.5"
            />
          ))}

          {/* horns: curved, banded */}
          <path
            d="M58 46 C50 30 48 16 58 2 C62 16 66 30 72 42 Z"
            fill={PAPER}
            stroke={edge}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M102 46 C110 30 112 16 102 2 C98 16 94 30 88 42 Z"
            fill={PAPER}
            stroke={edge}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M55 28 L64 25 M53 18 L60 15 M105 28 L96 25 M107 18 L100 15"
            stroke={INK}
            strokeWidth="1.3"
            strokeLinecap="round"
          />

          {/* body */}
          <path d={body} fill={RED} />
          <g clipPath={`url(#b${uid})`}>
            <ellipse
              cx={CX}
              cy={114}
              rx={20 + 12 * f}
              ry={17 + 7 * f}
              fill={BELLY}
            />
            {detail && (
              <rect
                x={CX + 18}
                y="20"
                width="80"
                height="140"
                fill={`url(#h${uid})`}
                opacity="0.22"
              />
            )}
            <ellipse
              cx={CX - 26}
              cy={52}
              rx={12}
              ry={7}
              fill="#fff"
              opacity="0.22"
              transform={`rotate(-30 ${CX - 26} 52)`}
            />
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
              <path
                d="M50 96 q8 -4 14 0 M48 104 q8 -4 15 0 M50 112 q7 -3 12 0 M110 96 q-8 -4 -14 0 M112 104 q-8 -4 -15 0 M110 112 q-7 -3 -12 0"
                fill="none"
                stroke={INK}
                strokeWidth="1.6"
                strokeLinecap="round"
                opacity="0.55"
              />
            )}
          </g>
          <path d={body} fill="none" stroke={edge} strokeWidth="1.8" />

          {/* hair tuft between the horns */}
          <path
            d="M66 40 q3 -12 9 -4 q3 -11 10 -1 q4 -10 9 4 q-14 6 -28 1 Z"
            fill={INK}
          />

          {mood === "proud" && (
            <g>
              <path
                d={`M${CX - 52} 52 Q${CX} 44 ${CX + 52} 52 L${CX + 53} 62 Q${CX} 54 ${CX - 53} 62 Z`}
                fill={PAPER}
                stroke={INK}
                strokeWidth="1.5"
              />
              <circle cx={CX} cy={53} r="4.5" fill={RED} />
            </g>
          )}

          {/* arms: body-red capsules with an ink edge, then a hand */}
          {arms(mood, f, wave, t).map((a, i) => (
            <g key={i}>
              <line
                x1={a.shoulder[0]}
                y1={a.shoulder[1]}
                x2={a.hand[0]}
                y2={a.hand[1]}
                stroke={edge}
                strokeWidth="14"
                strokeLinecap="round"
              />
              <line
                x1={a.shoulder[0]}
                y1={a.shoulder[1]}
                x2={a.hand[0]}
                y2={a.hand[1]}
                stroke={RED}
                strokeWidth="10.5"
                strokeLinecap="round"
              />
              <circle
                cx={a.hand[0]}
                cy={a.hand[1]}
                r="7"
                fill={RED}
                stroke={edge}
                strokeWidth="1.5"
              />
            </g>
          ))}

          <Face mood={mood} t={t} lid={lidAt(t)} look={look} />
          {chomp > 0.01 && (
            <g>
              <ellipse
                cx={CX}
                cy={106}
                rx={14 + 6 * chomp}
                ry={3 + 14 * chomp}
                fill={INK}
              />
              <ellipse
                cx={CX}
                cy={106 + 9 * chomp}
                rx={8 * chomp}
                ry={5 * chomp}
                fill={BLUSH}
              />
              <path
                d={`M70 ${103 - 12 * chomp} l3 7 l3 -7 Z M84 ${103 - 12 * chomp} l3 7 l3 -7 Z`}
                fill={PAPER}
                stroke={INK}
                strokeWidth="1"
              />
            </g>
          )}
        </g>
      </svg>

      {mood === "starving" && size >= 44 && (
        <span
          aria-hidden="true"
          lang="ja"
          style={{
            position: "absolute",
            right: -size * 0.16,
            top: size * 0.52,
            fontFamily: display,
            fontSize: Math.max(10, size * 0.14),
            color: night ? PAPER : INK,
            rotate: "-12deg",
            translate: `0px ${Math.sin(t * 2.6) * size * 0.03}px`,
            scale: String(1 + 0.18 * Math.max(0, Math.sin(t * 3.1))),
            opacity: 0.6 + 0.4 * Math.abs(Math.sin(t * 1.3)),
          }}
        >
          ぐぅ
        </span>
      )}
      {mood === "sleepy" && (
        <>
          <Z
            right={-6}
            top={6}
            size={size * 0.16}
            phase={(t % 2.6) / 2.6}
            night={night}
          />
          <Z
            right={-14}
            top={0}
            size={size * 0.12}
            phase={((t + 1.3) % 2.6) / 2.6}
            night={night}
          />
        </>
      )}
    </span>
  );
}

function Face({
  mood,
  t,
  lid,
  look,
}: {
  mood: Mood;
  t: number;
  lid: number;
  look: readonly [number, number];
}) {
  const lx = look[0] * 4;
  const ly = look[1] * 3;
  // Lids close from the top in body red, so they read as the oni's own skin.
  const lids =
    lid > 0.01 ? (
      <g fill={RED} stroke={INK} strokeWidth="1.5">
        <ellipse cx="62" cy={69 + 11 * lid} rx="12" ry={11 * lid} />
        <ellipse cx="98" cy={69 + 11 * lid} rx="12" ry={11 * lid} />
      </g>
    ) : null;
  const drop = (t % 1.8) / 1.8;
  const spin = (cx: number, cy: number) =>
    `rotate(${(t * 90) % 360} ${cx} ${cy})`;
  const cheeks = (
    <g fill={BLUSH} opacity="0.8">
      <ellipse cx="54" cy="96" rx="8" ry="4" />
      <ellipse cx="106" cy="96" rx="8" ry="4" />
    </g>
  );
  // Two small tusks pointing up from the lower lip.
  const tusks = (y: number) => (
    <path
      d={`M68 ${y} l3 -7 l3 7 Z M86 ${y} l3 -7 l3 7 Z`}
      fill={PAPER}
      stroke={INK}
      strokeWidth="1"
      strokeLinejoin="round"
    />
  );
  const brow = (d: string) => (
    <path
      d={d}
      fill="none"
      stroke={INK}
      strokeWidth="5"
      strokeLinecap="round"
    />
  );
  switch (mood) {
    case "starving":
      return (
        <g>
          {brow("M52 66 L66 60 M108 66 L94 60")}
          <circle
            cx="62"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle
            cx="98"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle cx={62 + lx} cy={85 + ly} r="3.2" fill={INK} />
          <circle cx={98 + lx} cy={85 + ly} r="3.2" fill={INK} />
          {lids}
          <path
            d="M64 100 q4 -5 8 0 t8 0 t8 0 t8 0 V108 a16 10 0 0 1 -32 0 Z"
            fill={INK}
          />
          <path
            d="M86 108 q2 8 0 12 q-3 -2 -2 -6"
            fill="#8FB3D9"
            stroke={INK}
            strokeWidth="1"
          />
          <path
            d="M120 48 q6 10 0 14 q-6 -4 0 -14 Z"
            fill="#8FB3D9"
            stroke={INK}
            strokeWidth="1.2"
            transform={`translate(${drop * 3} ${drop * 18})`}
            opacity={1 - drop}
          />
        </g>
      );
    case "fed":
      return (
        <g>
          {brow("M50 66 q10 -6 20 0 M90 66 q10 -6 20 0")}
          <path
            d="M52 82 a10 10 0 0 1 20 0 M88 82 a10 10 0 0 1 20 0"
            fill="none"
            stroke={INK}
            strokeWidth="5"
            strokeLinecap="round"
          />
          {cheeks}
          <path d="M60 98 h40 v4 a20 18 0 0 1 -40 0 Z" fill={INK} />
          <path d="M70 114 a10 7 0 0 1 20 0 Z" fill={BLUSH} />
          {tusks(99)}
          <path
            d="M28 40 l3 6 l6 1 l-5 4 l1 6 l-5 -3 l-5 3 l1 -6 l-5 -4 l6 -1 Z"
            fill={TIGER}
            stroke={INK}
            strokeWidth="1"
            transform={spin(28, 48)}
          />
          <path
            d="M136 34 l2 4 l4 1 l-3 3 l1 4 l-4 -2 l-4 2 l1 -4 l-3 -3 l4 -1 Z"
            fill={TIGER}
            stroke={INK}
            strokeWidth="1"
            transform={spin(136, 40)}
          />
        </g>
      );
    case "proud":
      return (
        <g>
          {brow("M50 70 l18 -3 M110 70 l-18 -3")}
          <path
            d="M52 84 a10 8 0 0 1 20 0 M88 84 a10 8 0 0 1 20 0"
            fill="none"
            stroke={INK}
            strokeWidth="5"
            strokeLinecap="round"
          />
          {cheeks}
          <path
            d="M62 100 q18 14 36 0"
            fill="none"
            stroke={INK}
            strokeWidth="5"
            strokeLinecap="round"
          />
          {tusks(104)}
        </g>
      );
    case "sleepy":
      return (
        <g>
          <path
            d="M52 82 a10 7 0 0 0 20 0 M88 82 a10 7 0 0 0 20 0"
            fill="none"
            stroke={INK}
            strokeWidth="5"
            strokeLinecap="round"
          />
          {cheeks}
          <ellipse cx="80" cy="104" rx="7" ry="5.5" fill={INK} />
        </g>
      );
    case "restless":
      return (
        <g>
          {brow("M52 64 L68 68 M108 64 L92 68")}
          <circle
            cx="62"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle
            cx="98"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle cx={66 + lx} cy={78 + ly} r="5" fill={INK} />
          <circle cx={102 + lx} cy={78 + ly} r="5" fill={INK} />
          {lids}
          <path
            d="M60 104 q5 -6 10 0 t10 0 t10 0 t10 0"
            fill="none"
            stroke={INK}
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path
            d="M122 48 q6 10 0 14 q-6 -4 0 -14 Z"
            fill="#8FB3D9"
            stroke={INK}
            strokeWidth="1.2"
          />
        </g>
      );
    default:
      return (
        <g>
          {brow("M52 66 h16 M92 66 h16")}
          <circle
            cx="62"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle
            cx="98"
            cy="80"
            r="11"
            fill="#fff"
            stroke={INK}
            strokeWidth="1.5"
          />
          <circle cx={64 + lx} cy={82 + ly} r="5" fill={INK} />
          <circle cx={96 + lx} cy={82 + ly} r="5" fill={INK} />
          {lids}
          {cheeks}
          <path
            d="M64 100 h32 v3 a10 10 0 0 1 -10 9 h-12 a10 10 0 0 1 -10 -9 Z"
            fill={INK}
          />
          {tusks(101)}
        </g>
      );
  }
}

function Z({
  right,
  top,
  size,
  phase,
  night,
}: {
  readonly right: number;
  readonly top: number;
  readonly size: number;
  readonly phase: number;
  readonly night: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        right,
        top,
        fontFamily: display,
        fontSize: Math.max(10, size),
        color: night ? PAPER : INK,
        opacity: 1 - phase,
        translate: `${phase * 8}px ${-phase * 18}px`,
      }}
    >
      z
    </span>
  );
}
