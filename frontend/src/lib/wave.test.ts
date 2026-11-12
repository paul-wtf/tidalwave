import { describe, expect, it } from 'vitest';
import { WAVE_HEIGHT, WAVE_WIDTH, wavePaths, waveRidges } from './wave';

const rising = Array.from({ length: 30 }, (_, i) => i);
const peak = Array.from({ length: 31 }, (_, i) => 15 - Math.abs(i - 15));

describe('waveRidges', () => {
  it('has no wave without a trend', () => {
    expect(waveRidges([])).toEqual([]);
    expect(waveRidges([12])).toEqual([]);
    expect(waveRidges([0, 0, 0, 0])).toEqual([]);
  });

  it('draws four layers with the same number of knots', () => {
    const ridges = waveRidges(rising);
    expect(ridges).toHaveLength(4);
    expect(new Set(ridges.map((r) => r.length)).size).toBe(1);
  });

  it('rises where listening rises', () => {
    for (const ridge of waveRidges(rising)) {
      expect(ridge[ridge.length - 1]).toBeLessThan(ridge[0]);
    }
    const back = waveRidges(rising)[0];
    expect([...back].sort((a, b) => b - a)).toEqual(back);
  });

  it('crests where listening peaks', () => {
    const back = waveRidges(peak)[0];
    const crest = back.indexOf(Math.min(...back));
    expect(crest).toBe((back.length - 1) / 2);
  });

  it('follows the shape, not the scale', () => {
    expect(waveRidges(rising.map((v) => v * 1000))).toEqual(waveRidges(rising));
  });

  it('keeps the front layers lower and calmer than the back one', () => {
    const ridges = waveRidges(peak);
    const swing = (r: number[]) => Math.max(...r) - Math.min(...r);
    for (let i = 1; i < ridges.length; i++) {
      expect(Math.max(...ridges[i])).toBeGreaterThan(Math.max(...ridges[i - 1]));
      expect(swing(ridges[i])).toBeLessThan(swing(ridges[i - 1]));
    }
  });

  it('stays inside the picture', () => {
    for (const series of [rising, peak, [0, 0, 500, 0, 0], [1, 1]]) {
      for (const y of waveRidges(series).flat()) {
        expect(y).toBeGreaterThan(WAVE_HEIGHT * 0.4);
        expect(y).toBeLessThan(WAVE_HEIGHT);
      }
    }
  });
});

describe('wavePaths', () => {
  it('returns no paths without a trend', () => {
    expect(wavePaths([])).toEqual([]);
  });

  it('closes every layer along the bottom edge', () => {
    const paths = wavePaths(peak);
    expect(paths).toHaveLength(4);
    for (const d of paths) {
      expect(d.startsWith('M0,')).toBe(true);
      expect(d.endsWith(`L${WAVE_WIDTH},${WAVE_HEIGHT} L0,${WAVE_HEIGHT} Z`)).toBe(true);
    }
  });

  it('keeps the same commands for any series so one wave can morph into the next', () => {
    const shape = (d: string) => d.replace(/-?\d+(\.\d+)?/g, 'n');
    expect(wavePaths(rising).map(shape)).toEqual(wavePaths([3, 9, 1]).map(shape));
  });
});
