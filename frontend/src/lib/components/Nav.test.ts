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

  it('has no Admin link unless asked for one', () => {
    render(Nav);
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull();
  });

  it('ends with an Admin link for admins', () => {
    render(Nav, { admin: true });
    const links = screen.getAllByRole('link');
    expect(links.at(-1)).toHaveTextContent('Admin');
    expect(links.at(-1)).toHaveAttribute('href', '/admin');
  });

  it('lists Compare after Insights', () => {
    render(Nav);
    const labels = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels.indexOf('Compare')).toBe(labels.indexOf('Insights') + 1);
  });
});
