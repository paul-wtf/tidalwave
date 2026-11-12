// frontend/src/lib/components/WeekdayChart.test.ts
import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import WeekdayChart from './WeekdayChart.svelte';

describe('WeekdayChart', () => {
  it('renders a labelled region for the weekday distribution', () => {
    render(WeekdayChart, { props: { days: [3, 0, 1, 0, 5, 0, 2] } });
    // The chart exposes an accessible label + a total summary for non-visual users.
    expect(screen.getByRole('img', { name: /listens by weekday/i })).toBeInTheDocument();
    expect(screen.getByText(/11 listens/i)).toBeInTheDocument(); // 3+1+5+2 = 11
  });

  it('keeps the caption and the summary outside the image, where screen readers reach them', () => {
    render(WeekdayChart, { props: { days: [3, 0, 1, 0, 5, 0, 2] } });
    expect(screen.getByText('By weekday').closest('[role="img"]')).toBeNull();
    expect(screen.getByText(/11 listens/i).closest('[role="img"]')).toBeNull();
  });
});
