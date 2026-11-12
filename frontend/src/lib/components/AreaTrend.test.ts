import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import AreaTrend from './AreaTrend.svelte';

describe('AreaTrend', () => {
  it('renders an accessible region titled by its prop', () => {
    render(AreaTrend, { props: {
      title: 'Listens over time',
      points: [{ period: '2024-06-01T00:00:00', value: 3 }, { period: '2024-06-02T00:00:00', value: 5 }]
    } });
    expect(screen.getByRole('img', { name: /listens over time/i })).toBeInTheDocument();
  });

  it('shows a bucket selector when bucket controls are provided', async () => {
    const onBucketChange = vi.fn();
    render(AreaTrend, { props: {
      title: 'Over time',
      points: [{ period: '2024-06-01T00:00:00', value: 3 }],
      bucket: 'day',
      onBucketChange
    } });
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /bucket/i }), 'week');
    expect(onBucketChange).toHaveBeenCalledWith('week');
  });

  it('keeps the title, the bucket selector and the empty note outside the image', () => {
    render(AreaTrend, { props: {
      title: 'Over time', points: [{ period: '2024-06-01T00:00:00', value: 3 }],
      bucket: 'day', onBucketChange: vi.fn()
    } });
    expect(screen.getByRole('combobox', { name: /bucket/i }).closest('[role="img"]')).toBeNull();
    expect(screen.getByText('Over time').closest('[role="img"]')).toBeNull();
  });

  it('says so in text when there is nothing to draw', () => {
    render(AreaTrend, { props: { title: 'Over time', points: [] } });
    expect(screen.getByText('No data yet.').closest('[role="img"]')).toBeNull();
  });

  const points = (values: number[]) =>
    values.map((value, i) => ({ period: `2024-06-0${i + 1}T00:00:00`, value }));

  it('marks the curve to be drawn in', () => {
    const { container } = render(AreaTrend, { props: { title: 'Trend', points: points([3, 5, 2]) } });
    expect(container.querySelector('svg')).toHaveClass('draw');
  });

  it('redraws the curve when the data changes and keeps it otherwise', async () => {
    const { container, rerender } = render(AreaTrend, {
      props: { title: 'Trend', points: points([3, 5, 2]) }
    });
    const first = container.querySelector('svg');
    await rerender({ points: points([3, 5, 2]) });
    expect(container.querySelector('svg')).toBe(first);
    await rerender({ points: points([1, 9, 4]) });
    expect(container.querySelector('svg')).not.toBe(first);
  });
});
