import type { Theme } from '$lib/stores/theme';

/** A colour's direction in OKLCH: hue in degrees and chroma. */
export interface CoverColor {
  hue: number;
  chroma: number;
}

export interface CoverAccent {
  accent: string;
  text: string;
  soft: string;
}

type Triple = [number, number, number];

const toLinear = (channel: number) => {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const toGamma = (c: number) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);

// Matrices from Björn Ottosson's Oklab reference (sRGB D65).
export function rgbToOklab(r: number, g: number, b: number): Triple {
  const lr = toLinear(r);
  const lg = toLinear(g);
  const lb = toLinear(b);
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  ];
}

function oklchToLinear(lightness: number, chroma: number, hue: number): Triple {
  const angle = (hue * Math.PI) / 180;
  const a = chroma * Math.cos(angle);
  const b = chroma * Math.sin(angle);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s
  ];
}

/** OKLCH to 8-bit sRGB. Chroma shrinks until the colour fits the gamut, so
 *  the lightness that contrast depends on is never traded away. */
export function oklchToRgb(lightness: number, chroma: number, hue: number): Triple {
  for (let c = chroma; ; c = Math.max(0, c - 0.004)) {
    const linear = oklchToLinear(lightness, c, hue);
    if (c === 0 || linear.every((v) => v >= -0.0005 && v <= 1.0005)) {
      return linear.map((v) => Math.round(255 * toGamma(Math.min(1, Math.max(0, v))))) as Triple;
    }
  }
}

const HUE_BINS = 24;
const MIN_CHROMA = 0.04;
const MIN_COLOURED_SHARE = 0.05;

/** The most present hue among the clearly coloured pixels of RGBA data, or
 *  null for a cover that is grey, black or white. */
export function dominantColor(pixels: ArrayLike<number>): CoverColor | null {
  const bins = Array.from({ length: HUE_BINS }, () => ({ a: 0, b: 0, weight: 0 }));
  let opaque = 0;
  let coloured = 0;
  for (let i = 0; i + 3 < pixels.length; i += 4) {
    if (pixels[i + 3] < 128) continue;
    opaque++;
    const [, a, b] = rgbToOklab(pixels[i], pixels[i + 1], pixels[i + 2]);
    const chroma = Math.hypot(a, b);
    if (chroma < MIN_CHROMA) continue;
    coloured++;
    const hue = (Math.atan2(b, a) * 180) / Math.PI;
    const bin = bins[Math.floor((((hue % 360) + 360) % 360) / (360 / HUE_BINS)) % HUE_BINS];
    bin.a += a;
    bin.b += b;
    bin.weight += chroma;
  }
  if (opaque === 0 || coloured / opaque < MIN_COLOURED_SHARE) return null;
  const around = (i: number) => [bins[(i + HUE_BINS - 1) % HUE_BINS], bins[i], bins[(i + 1) % HUE_BINS]];
  const weightAround = (i: number) => around(i).reduce((sum, bin) => sum + bin.weight, 0);
  let best = 0;
  for (let i = 1; i < HUE_BINS; i++) if (weightAround(i) > weightAround(best)) best = i;
  const group = around(best);
  const a = group.reduce((sum, bin) => sum + bin.a, 0);
  const b = group.reduce((sum, bin) => sum + bin.b, 0);
  const weight = weightAround(best);
  return {
    hue: (((Math.atan2(b, a) * 180) / Math.PI) % 360 + 360) % 360,
    chroma: Math.hypot(a, b) ** 2 / weight
  };
}

// Lightness is fixed per theme and chroma clamped, so every hue stays as
// readable as the stock mauve: at least 4.5:1 on crust, mantle and base.
const TONES: Record<Theme, { accent: number; text: number; chroma: [number, number]; soft: number }> = {
  mocha: { accent: 0.8, text: 0.8, chroma: [0.07, 0.13], soft: 0.25 },
  latte: { accent: 0.56, text: 0.48, chroma: [0.1, 0.2], soft: 0.18 }
};

const hex = (rgb: Triple) => '#' + rgb.map((v) => v.toString(16).padStart(2, '0')).join('');

export function coverAccent(color: CoverColor, theme: Theme): CoverAccent {
  const tone = TONES[theme];
  const chroma = Math.min(tone.chroma[1], Math.max(tone.chroma[0], color.chroma));
  const accent = oklchToRgb(tone.accent, chroma, color.hue);
  return {
    accent: hex(accent),
    text: hex(oklchToRgb(tone.text, chroma, color.hue)),
    soft: `rgba(${accent.join(', ')}, ${tone.soft})`
  };
}

const SAMPLE = 32;

/** Reads the cover through its own CORS-enabled Image, so a host without
 *  CORS headers only costs the colour. Never rejects. */
export function extractCoverColor(src: string): Promise<CoverColor | null> {
  return new Promise((resolve) => {
    try {
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.onerror = () => resolve(null);
      image.onload = () => {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = SAMPLE;
          canvas.height = SAMPLE;
          const context = canvas.getContext('2d', { willReadFrequently: true });
          if (!context) return resolve(null);
          context.drawImage(image, 0, 0, SAMPLE, SAMPLE);
          resolve(dominantColor(context.getImageData(0, 0, SAMPLE, SAMPLE).data));
        } catch {
          resolve(null);
        }
      };
      image.src = src;
    } catch {
      resolve(null);
    }
  });
}
