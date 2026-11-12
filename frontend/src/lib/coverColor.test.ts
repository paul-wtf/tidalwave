import { afterEach, describe, expect, it, vi } from 'vitest';
import { coverAccent, dominantColor, extractCoverColor, rgbToOklab } from './coverColor';

type Rgb = [number, number, number];

const pixels = (...runs: [Rgb, number][]) =>
  Uint8ClampedArray.from(runs.flatMap(([rgb, n]) => Array.from({ length: n }, () => [...rgb, 255]).flat()));
const hueOf = (rgb: Rgb) => {
  const [, a, b] = rgbToOklab(...rgb);
  return ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
};
const hueGap = (a: number, b: number) => Math.abs(((a - b + 540) % 360) - 180);
const rgbOf = (hex: string): Rgb => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as Rgb;
const luminance = (hex: string) => {
  const [r, g, b] = rgbOf(hex).map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const TEAL: Rgb = [31, 138, 138];
const ORANGE: Rgb = [217, 96, 26];

describe('dominantColor', () => {
  it('finds the hue that covers most of the image', () => {
    const color = dominantColor(pixels([TEAL, 700], [ORANGE, 200], [[40, 40, 40], 124]))!;
    expect(hueGap(color.hue, hueOf(TEAL))).toBeLessThan(8);
    expect(color.chroma).toBeGreaterThan(0.05);
  });

  it('prefers a coloured minority over white, grey and black', () => {
    const color = dominantColor(pixels([[250, 250, 250], 600], [[20, 20, 20], 250], [ORANGE, 174]))!;
    expect(hueGap(color.hue, hueOf(ORANGE))).toBeLessThan(8);
  });

  it('gives no colour for a grey cover', () => {
    expect(dominantColor(pixels([[120, 120, 120], 800], [[30, 30, 30], 224]))).toBeNull();
  });

  it('ignores transparent pixels and empty data', () => {
    expect(dominantColor(new Uint8ClampedArray(0))).toBeNull();
    const clear = Uint8ClampedArray.from(Array.from({ length: 50 }, () => [...ORANGE, 0]).flat());
    expect(dominantColor(clear)).toBeNull();
  });
});

describe('coverAccent', () => {
  const SURFACES = {
    mocha: ['#11111b', '#181825', '#1e1e2e'],
    latte: ['#dce0e8', '#e6e9ef', '#eff1f5']
  } as const;
  const hues = Array.from({ length: 72 }, (_, i) => i * 5);
  const chromas = [0, 0.03, 0.1, 0.2, 0.4];

  it.each(['mocha', 'latte'] as const)('keeps text at 4.5:1 or better on every %s surface', (theme) => {
    for (const hue of hues) for (const chroma of chromas) {
      const { text } = coverAccent({ hue, chroma }, theme);
      for (const surface of SURFACES[theme]) {
        expect(contrast(text, surface), `${text} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it.each(['mocha', 'latte'] as const)('keeps the chart colour at 3:1 or better in %s', (theme) => {
    for (const hue of hues) for (const chroma of chromas) {
      const { accent } = coverAccent({ hue, chroma }, theme);
      for (const surface of SURFACES[theme]) {
        expect(contrast(accent, surface), `${accent} on ${surface}`).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it('fixes lightness whatever the cover colour is', () => {
    const lightness = (hex: string) => rgbToOklab(...rgbOf(hex))[0];
    for (const hue of hues) {
      expect(lightness(coverAccent({ hue, chroma: 0.3 }, 'mocha').accent)).toBeCloseTo(0.8, 1);
      expect(lightness(coverAccent({ hue, chroma: 0.3 }, 'latte').accent)).toBeCloseTo(0.56, 1);
    }
  });

  it('clamps saturation at both ends and keeps the hue', () => {
    const chroma = (hex: string) => Math.hypot(...rgbToOklab(...rgbOf(hex)).slice(1));
    const vivid = coverAccent({ hue: 30, chroma: 0.4 }, 'mocha').accent;
    const dull = coverAccent({ hue: 30, chroma: 0.01 }, 'mocha').accent;
    expect(chroma(vivid)).toBeLessThanOrEqual(0.135);
    expect(chroma(dull)).toBeGreaterThanOrEqual(0.06);
    expect(hueGap(hueOf(rgbOf(vivid)), 30)).toBeLessThan(6);
    expect(hueGap(hueOf(rgbOf(dull)), 30)).toBeLessThan(6);
  });

  it('derives the soft tint from the accent', () => {
    const { accent, soft } = coverAccent({ hue: 200, chroma: 0.1 }, 'mocha');
    expect(soft).toBe(`rgba(${rgbOf(accent).join(', ')}, 0.25)`);
  });
});

describe('extractCoverColor', () => {
  afterEach(() => vi.unstubAllGlobals());

  class FakeImage {
    static last: FakeImage;
    static order: string[] = [];
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    constructor() {
      FakeImage.last = this;
      FakeImage.order = [];
    }
    set crossOrigin(value: string) {
      FakeImage.order.push(`crossOrigin=${value}`);
    }
    set src(value: string) {
      FakeImage.order.push(`src=${value}`);
    }
  }

  const stubCanvas = (context: unknown) => {
    const real = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) =>
      tag === 'canvas' ? { getContext: () => context } : real(tag)) as typeof document.createElement);
  };

  it('asks for the image with CORS before setting its source', async () => {
    vi.stubGlobal('Image', FakeImage);
    stubCanvas({ drawImage: () => {}, getImageData: () => ({ data: pixels([TEAL, 1024]) }) });
    const result = extractCoverColor('https://img.test/cover.jpg');
    expect(FakeImage.order).toEqual(['crossOrigin=anonymous', 'src=https://img.test/cover.jpg']);
    FakeImage.last.onload!();
    const color = await result;
    expect(hueGap(color!.hue, hueOf(TEAL))).toBeLessThan(8);
    vi.restoreAllMocks();
  });

  it('resolves to null when the image fails to load', async () => {
    vi.stubGlobal('Image', FakeImage);
    const result = extractCoverColor('https://img.test/cover.jpg');
    FakeImage.last.onerror!();
    expect(await result).toBeNull();
  });

  it('resolves to null when the canvas is tainted', async () => {
    vi.stubGlobal('Image', FakeImage);
    stubCanvas({
      drawImage: () => {},
      getImageData: () => {
        throw new DOMException('tainted', 'SecurityError');
      }
    });
    const result = extractCoverColor('https://img.test/cover.jpg');
    FakeImage.last.onload!();
    expect(await result).toBeNull();
    vi.restoreAllMocks();
  });

  it('resolves to null without a 2d context or without Image', async () => {
    vi.stubGlobal('Image', FakeImage);
    stubCanvas(null);
    const result = extractCoverColor('https://img.test/cover.jpg');
    FakeImage.last.onload!();
    expect(await result).toBeNull();
    vi.restoreAllMocks();
    vi.stubGlobal('Image', undefined);
    expect(await extractCoverColor('https://img.test/cover.jpg')).toBeNull();
  });
});
