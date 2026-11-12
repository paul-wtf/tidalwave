import { describe, expect, it } from 'vitest';
import { dialPoint, dialSector } from './dial';

const close = (point: [number, number], x: number, y: number) => {
  expect(point[0]).toBeCloseTo(x);
  expect(point[1]).toBeCloseTo(y);
};

describe('dialPoint', () => {
  it('puts midnight at the top and runs clockwise', () => {
    close(dialPoint(0, 10), 0, -10);
    close(dialPoint(6, 10), 10, 0);
    close(dialPoint(12, 10), 0, 10);
    close(dialPoint(18, 10), -10, 0);
  });
});

describe('dialSector', () => {
  it('spans one hour between the inner and outer radius', () => {
    const numbers = dialSector(0, 40, 80, 0).match(/-?\d+\.\d+/g)!.map(Number);
    const [x0, y0, x1, y1] = numbers;
    expect([x0, y0, x1, y1]).toEqual([0, -40, 0, -80]);
    const [endX, endY] = dialPoint(1, 80);
    expect(numbers).toContain(Number(endX.toFixed(2)));
    expect(numbers).toContain(Number(endY.toFixed(2)));
  });
});
