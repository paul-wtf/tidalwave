import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({ goto: (...a: unknown[]) => goto(...a) }));

import CompareView from './CompareView.svelte';
import { auth } from '$lib/stores/auth';
import { range } from '$lib/stores/range';
import { stubFetch } from '$lib/test/stubFetch';
import type { Comparison } from '$lib/api/client';

const data: Comparison = {
  id: 3, partner: 'bob', created_at: '2026-11-01T10:00:00Z',
  overlap: 0.4237, listens: { you: 1234, partner: 980 }, shared_artists: 12,
  shared: [{ artist: 'Kavinsky', you: 60, partner: 20 }, { artist: 'Daft Punk', you: 3, partner: 40 }],
  only_you: [{ artist: 'Timecop1983', count: 22 }],
  only_partner: [{ artist: 'Perturbator', count: 31 }]
};

describe('CompareView', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'alice', timezone: 'UTC' } as never, loading: false });
    range.set({ kind: 'calendar', key: 'last_month' });
  });

  it('asks for the pair with the selected range', async () => {
    const seen = stubFetch(() => Response.json(data));
    render(CompareView, { id: 3 });
    await screen.findByText('42%');
    expect(seen[0]).toMatch(/^GET \/comparisons\/3\?start=\d{4}-\d{2}-01&end=\d{4}-\d{2}-01/);
  });

  it('shows the overlap and names how it is measured', async () => {
    stubFetch(() => Response.json(data));
    render(CompareView, { id: 3 });
    expect(await screen.findByRole('heading', { name: 'You and bob' })).toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText(/smaller of your two shares/)).toBeInTheDocument();
    expect(screen.getByText(/12 artists in common/)).toBeInTheDocument();
  });

  it('lists shared artists with both counts and what only one side heard', async () => {
    stubFetch(() => Response.json(data));
    render(CompareView, { id: 3 });
    const shared = await screen.findByRole('region', { name: 'Shared artists' });
    const kavinsky = within(shared).getByRole('listitem', { name: 'Kavinsky' });
    expect(kavinsky).toHaveTextContent('you 60');
    expect(kavinsky).toHaveTextContent('bob 20');
    expect(within(screen.getByRole('region', { name: 'Only you' })).getByText('Timecop1983')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Only bob' })).getByText('Perturbator')).toBeInTheDocument();
  });

  it('has no overlap figure when a side has no listens', async () => {
    stubFetch(() => Response.json({ ...data, overlap: null, listens: { you: 5, partner: 0 }, shared: [], shared_artists: 0 }));
    render(CompareView, { id: 3 });
    expect(await screen.findByText(/bob has no listens in this range/)).toBeInTheDocument();
    expect(screen.queryByText('0%')).toBeNull();
  });

  it('says when the comparison is gone', async () => {
    stubFetch(() => new Response('{}', { status: 404 }));
    render(CompareView, { id: 3 });
    expect(await screen.findByText(/no longer exists/)).toBeInTheDocument();
  });

  it('ends the comparison after confirming and goes back to the list', async () => {
    const seen = stubFetch((m) => (m === 'GET' ? Response.json(data) : undefined));
    render(CompareView, { id: 3 });
    await userEvent.click(await screen.findByRole('button', { name: 'End comparison' }));
    await userEvent.click(screen.getByRole('button', { name: 'End it for both of us' }));
    expect(seen).toContain('DELETE /comparisons/3');
    await vi.waitFor(() => expect(goto).toHaveBeenCalledWith('/compare'));
  });
});
