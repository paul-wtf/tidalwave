import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { wavePaths } from '$lib/wave';
import TrendWave from './TrendWave.svelte';

describe('TrendWave', () => {
  it('renders nothing without a trend so the static background stays', () => {
    const { container } = render(TrendWave, { values: [] });
    expect(container.querySelector('.wave')).toBeNull();
  });

  it('draws the four wave layers from the trend', () => {
    const values = [3, 8, 2, 9, 4];
    const { container } = render(TrendWave, { values });
    const layers = Array.from(container.querySelectorAll('path.layer'));
    expect(layers.map((p) => p.getAttribute('d'))).toEqual(wavePaths(values));
  });

  it('is decorative only', () => {
    const { container } = render(TrendWave, { values: [3, 8, 2] });
    const wave = container.querySelector('.wave')!;
    expect(wave).toHaveAttribute('aria-hidden', 'true');
    expect(wave.querySelector('title, text, a, [tabindex]')).toBeNull();
  });

  it('stretches the ridges over the whole viewport so the full range stays in view', () => {
    const { container } = render(TrendWave, { values: [3, 8, 2] });
    expect(container.querySelector('svg.ridges')).toHaveAttribute('preserveAspectRatio', 'none');
    expect(container.querySelector('svg.ridges circle')).toBeNull();
    expect(container.querySelector('svg.sky')).toHaveAttribute('preserveAspectRatio', 'xMidYMax slice');
  });

  it('removes the wave when the trend goes away', async () => {
    const { container, rerender } = render(TrendWave, { values: [3, 8, 2] });
    expect(container.querySelector('.wave')).not.toBeNull();
    await rerender({ values: [0, 0, 0] });
    expect(container.querySelector('.wave')).toBeNull();
  });
});
