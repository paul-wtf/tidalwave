import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';

vi.mock('$app/stores', async () => {
  const { readable } = await import('svelte/store');
  return { page: readable({ url: new URL('http://localhost/insights') }) };
});

import Nav from './Nav.svelte';

describe('Nav', () => {
  it('lists Insights after Albums by default', () => {
    render(Nav);
    const labels = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels.indexOf('Insights')).toBe(labels.indexOf('Albums') + 1);
    expect(screen.getByRole('link', { name: 'Insights' })).toHaveAttribute('href', '/insights');
    expect(screen.getByRole('link', { name: 'Insights' })).toHaveAttribute('aria-current', 'page');
  });
});
