import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ListeningClock from './ListeningClock.svelte';

const hours = new Array(24).fill(0);

describe('ListeningClock', () => {
  it('names the timezone in the caption', () => {
    render(ListeningClock, { hours, tz: 'Europe/Berlin' });
    expect(screen.getByText('By hour (Europe/Berlin)')).toBeInTheDocument();
  });

  it('says local time in share views', () => {
    render(ListeningClock, { hours, tz: null });
    expect(screen.getByText('By hour (local time)')).toBeInTheDocument();
  });
});
