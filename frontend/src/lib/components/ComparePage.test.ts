import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import ComparePage from './ComparePage.svelte';
import { auth } from '$lib/stores/auth';
import { stubFetch } from '$lib/test/stubFetch';
import type { Comparisons } from '$lib/api/client';

const TOKEN = 'T'.repeat(43);
const overview: Comparisons = {
  pairs: [{ id: 3, partner: 'bob', created_at: '2026-11-01T10:00:00Z' }],
  invites: [{ token: TOKEN, created_at: '2026-11-10T10:00:00Z' }]
};

describe('ComparePage', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'alice', timezone: 'UTC' } as never, loading: false });
  });

  it('lists pairs with a link and open invites with their link', async () => {
    stubFetch((m, url) => (url === '/comparisons' ? Response.json(overview) : undefined));
    render(ComparePage);
    expect(await screen.findByRole('link', { name: 'bob' })).toHaveAttribute('href', '/compare/3');
    expect(screen.getByText(`${location.origin}/compare/invite/${TOKEN}`)).toBeInTheDocument();
  });

  it('creates an invite and shows its link', async () => {
    const seen = stubFetch((m, url) => {
      if (url === '/comparisons') return Response.json({ pairs: [], invites: [] });
      if (m === 'POST' && url === '/comparisons/invites') {
        return Response.json({ token: 'NEW', created_at: '2026-11-12T10:00:00Z' }, { status: 201 });
      }
    });
    render(ComparePage);
    await userEvent.click(await screen.findByRole('button', { name: 'Create invite link' }));
    expect(seen).toContain('POST /comparisons/invites');
    expect(await screen.findByText(`${location.origin}/compare/invite/NEW`)).toBeInTheDocument();
  });

  it('revokes an invite', async () => {
    const seen = stubFetch((m, url) => (url === '/comparisons' ? Response.json(overview) : undefined));
    render(ComparePage);
    const invite = await screen.findByRole('listitem', { name: 'Invite link' });
    await userEvent.click(within(invite).getByRole('button', { name: 'Revoke' }));
    expect(seen).toContain(`DELETE /comparisons/invites/${TOKEN}`);
    await vi.waitFor(() => expect(screen.queryByRole('listitem', { name: 'Invite link' })).toBeNull());
  });

  it('ends a pair only after confirming', async () => {
    const seen = stubFetch((m, url) => (url === '/comparisons' ? Response.json(overview) : undefined));
    render(ComparePage);
    const pair = await screen.findByRole('listitem', { name: 'bob' });
    await userEvent.click(within(pair).getByRole('button', { name: 'End' }));
    expect(seen.filter((s) => s.startsWith('DELETE'))).toEqual([]);
    expect(pair).toHaveTextContent(/stop seeing each other/);
    await userEvent.click(within(pair).getByRole('button', { name: 'End comparison' }));
    expect(seen).toContain('DELETE /comparisons/3');
    await vi.waitFor(() => expect(screen.queryByRole('link', { name: 'bob' })).toBeNull());
  });
});
