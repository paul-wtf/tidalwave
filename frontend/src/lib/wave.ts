export const WAVE_WIDTH = 1600;
export const WAVE_HEIGHT = 900;

const KNOTS = 17;
const SAMPLES = 9;

// Resting height and swing per layer, back to front, inside the band the
// static ridgelines of the wallpaper occupy (y 430 to 820 of 900).
const LAYERS = [
  { base: 600, swing: 170 },
  { base: 675, swing: 130 },
  { base: 755, swing: 95 },
  { base: 825, swing: 60 }
];

function sample(series: number[], position: number): number {
  const p = Math.min(series.length - 1, Math.max(0, position));
  const i = Math.floor(p);
  const next = Math.min(series.length - 1, i + 1);
  return series[i] + (series[next] - series[i]) * (p - i);
}

/** Ridge heights (y, top is 0) per layer, back to front. The back layer
 *  tracks the trend; each layer in front averages a wider window and trails
 *  half a knot further behind, so the crests roll instead of stacking. Empty
 *  without a trend. */
export function waveRidges(values: number[]): number[][] {
  const max = Math.max(0, ...values);
  if (values.length < 2 || max === 0) return [];
  const series = values.map((v) => Math.max(0, v) / max);
  const step = (series.length - 1) / (KNOTS - 1);
  return LAYERS.map(({ base, swing }, layer) =>
    Array.from({ length: KNOTS }, (_, knot) => {
      const reach = step * (0.5 + 0.4 * layer);
      const centre = (knot - 0.5 * layer) * step;
      let sum = 0;
      for (let s = 0; s < SAMPLES; s++) {
        sum += sample(series, centre + reach * ((2 * s) / (SAMPLES - 1) - 1));
      }
      return Math.round((base - swing * (sum / SAMPLES)) * 10) / 10;
    })
  );
}

const fixed = (v: number) => String(Math.round(v * 10) / 10);

export function wavePaths(values: number[]): string[] {
  return waveRidges(values).map((ridge) => {
    const last = ridge.length - 1;
    const gap = WAVE_WIDTH / last;
    const y = (i: number) => ridge[Math.min(last, Math.max(0, i))];
    let d = `M0,${fixed(y(0))}`;
    for (let i = 0; i < last; i++) {
      const out = y(i) + (y(i + 1) - y(i - 1)) / 6;
      const into = y(i + 1) - (y(i + 2) - y(i)) / 6;
      d +=
        ` C${fixed(i * gap + gap / 3)},${fixed(out)}` +
        ` ${fixed((i + 1) * gap - gap / 3)},${fixed(into)}` +
        ` ${fixed((i + 1) * gap)},${fixed(y(i + 1))}`;
    }
    return `${d} L${WAVE_WIDTH},${WAVE_HEIGHT} L0,${WAVE_HEIGHT} Z`;
  });
}
