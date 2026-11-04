// The app's "Tokyo street" print system (web/src/styles.css): washi ground, sumi ink,
// shu for the monster, ai for your day.
import { loadFont as loadDisplay } from "@remotion/google-fonts/DelaGothicOne";
import { loadFont as loadBody } from "@remotion/google-fonts/ZenKakuGothicNew";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const display = loadDisplay("normal", {
  weights: ["400"],
  subsets: ["latin", "japanese"],
}).fontFamily;
export const body = loadBody("normal", {
  weights: ["400", "700"],
  subsets: ["latin", "japanese"],
}).fontFamily;
export const mono = loadMono("normal", {
  weights: ["700"],
  subsets: ["latin"],
}).fontFamily;

export const C = {
  washi: "#f3eee5",
  paper: "#e8e1d4",
  paper3: "#dcd3c3",
  sumi: "#2b2724",
  shu: "#c4472f",
  ai: "#34506b",
  tiger: "#e9b43c",
  muted: "#6f665d",
};
