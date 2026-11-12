import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import { stubFetch } from '$lib/test/stubFetch';

vi.mock('$app/stores', async () => {
  const { readable } = await import('svelte/store');
  return { page: readable({ url: new URL('http://localhost/s/tok') }) };
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

import SharedLayout from './[token]/+layout.svelte';

describe('shared layout', () => {
  it('links to the review of the latest year the share covers', async () => {
    stubFetch((_, url) =>
      url === '/shared/tok/years' ? Response.json([{ year: 2025, listens: 9 }]) : undefined
    );
    render(SharedLayout, { data: { token: 'tok' } });
    expect(await screen.findByRole('link', { name: '2025' })).toHaveAttribute('href', '/s/tok/year/2025');
  });

  it('has no year link when the share covers no whole year', async () => {
    const seen = stubFetch((_, url) => (url === '/shared/tok/years' ? Response.json([]) : undefined));
    render(SharedLayout, { data: { token: 'tok' } });
    await vi.waitFor(() => expect(seen).toContain('GET /shared/tok/years'));
    expect(screen.queryByRole('link', { name: /^\d{4}$/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'Insights' })).toBeInTheDocument();
  });
});
