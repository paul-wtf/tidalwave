import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { goto } from '$app/navigation';
import YearIndex from './YearIndex.svelte';
import { stubFetch } from '$lib/test/stubFetch';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

describe('YearIndex', () => {
  beforeEach(() => vi.mocked(goto).mockClear());

  it('opens the latest year with listens', async () => {
    stubFetch((_, url) =>
      url === '/stats/years' ? Response.json([{ year: 2026, listens: 4 }, { year: 2025, listens: 9 }]) : undefined
    );
    render(YearIndex);
    await vi.waitFor(() => expect(goto).toHaveBeenCalledWith('/year/2026', { replaceState: true }));
  });

  it('stays inside a share', async () => {
    stubFetch((_, url) =>
      url === '/shared/tok/years' ? Response.json([{ year: 2025, listens: 9 }]) : undefined
    );
    render(YearIndex, { token: 'tok' });
    await vi.waitFor(() => expect(goto).toHaveBeenCalledWith('/s/tok/year/2025', { replaceState: true }));
  });

  it('says when there is no year to show', async () => {
    stubFetch((_, url) => (url === '/shared/tok/years' ? Response.json([]) : undefined));
    render(YearIndex, { token: 'tok' });
    expect(await screen.findByText('This share does not cover a whole year.')).toBeInTheDocument();
    expect(goto).not.toHaveBeenCalled();
  });
});
