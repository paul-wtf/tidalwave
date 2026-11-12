import { render, screen } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { formatDuration } from '$lib/format';
import StatCard from './StatCard.svelte';

describe('StatCard delta', () => {
  it('shows a positive change with plus sign and accessible label', () => {
    render(StatCard, { label: 'Songs', value: '10', delta: 0.12 });
    const el = screen.getByText('+12 % vs. previous');
    expect(el).toHaveClass('up');
    expect(el).toHaveAttribute('aria-label', '12 % more than the previous period');
  });

  it('shows a negative change with a real minus sign', () => {
    render(StatCard, { label: 'Songs', value: '10', delta: -0.08 });
    const el = screen.getByText('−8 % vs. previous');
    expect(el).toHaveClass('down');
    expect(el).toHaveAttribute('aria-label', '8 % less than the previous period');
  });

  it('shows a neutral zero change', () => {
    render(StatCard, { label: 'Songs', value: '10', delta: 0 });
    const el = screen.getByText('±0 % vs. previous');
    expect(el).toHaveClass('flat');
    expect(el).toHaveAttribute('aria-label', 'No change from the previous period');
  });

  it('treats changes that round to zero as neutral', () => {
    render(StatCard, { label: 'Songs', value: '10', delta: 0.003 });
    expect(screen.getByText('±0 % vs. previous')).toBeInTheDocument();
  });

  it('renders nothing for null or missing delta', () => {
    const { unmount } = render(StatCard, { label: 'Songs', value: '10', delta: null });
    expect(screen.queryByText(/vs\. previous/)).toBeNull();
    unmount();
    render(StatCard, { label: 'Songs', value: '10' });
    expect(screen.queryByText(/vs\. previous/)).toBeNull();
  });
});

describe('StatCard compact', () => {
  it('marks text values as compact', () => {
    render(StatCard, { label: 'First listen', value: '7 Nov 2024', compact: true });
    expect(screen.getByText('7 Nov 2024')).toHaveClass('compact');
  });
  it('is not compact by default', () => {
    render(StatCard, { label: 'Songs', value: '10' });
    expect(screen.getByText('10')).not.toHaveClass('compact');
  });
});

describe('StatCard numbers', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const allowMotion = () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query }));
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] });
  };
  const shown = (c: HTMLElement) => Number(c.querySelector('.value')!.textContent!.replace(/,/g, ''));
  const advance = (ms: number) => {
    vi.advanceTimersByTime(ms);
    flushSync();
  };

  it('formats a number as a count and shows it at once under reduced motion', () => {
    render(StatCard, { label: 'Songs', value: 1237 });
    expect(screen.getByText('1,237')).toBeInTheDocument();
  });

  it('applies a custom format to numbers', () => {
    render(StatCard, { label: 'Time', value: 7200, format: formatDuration });
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
  });

  it('counts up from zero when it appears', () => {
    allowMotion();
    const { container } = render(StatCard, { label: 'Songs', value: 1000 });
    expect(shown(container)).toBe(0);
    advance(300);
    expect(shown(container)).toBeGreaterThan(0);
    expect(shown(container)).toBeLessThan(1000);
    advance(2000);
    expect(shown(container)).toBe(1000);
  });

  it('moves from the shown number to the new one when the value changes', async () => {
    allowMotion();
    const { container, rerender } = render(StatCard, { label: 'Songs', value: 1000 });
    advance(2000);
    await rerender({ value: 400 });
    advance(300);
    expect(shown(container)).toBeGreaterThan(400);
    expect(shown(container)).toBeLessThan(1000);
    advance(2000);
    expect(shown(container)).toBe(400);
  });
});
