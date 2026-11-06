import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
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
