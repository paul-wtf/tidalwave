import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({ goto: (...a: unknown[]) => goto(...a) }));

import InviteAccept from './InviteAccept.svelte';
import { stubFetch } from '$lib/test/stubFetch';

describe('InviteAccept', () => {
  it('names the inviter and what both will see', async () => {
    stubFetch((m, url) => (url === '/comparisons/invites/T' ? Response.json({ inviter: 'bob', own: false }) : undefined));
    render(InviteAccept, { token: 'T' });
    expect(await screen.findByRole('heading', { name: 'bob wants to compare listening with you' })).toBeInTheDocument();
    expect(screen.getByText(/each other's top artists/)).toBeInTheDocument();
  });

  it('accepting stores the pair and opens it', async () => {
    const seen = stubFetch((m, url) => {
      if (url === '/comparisons/invites/T') return Response.json({ inviter: 'bob', own: false });
      if (url === '/comparisons/invites/T/accept') {
        return Response.json({ id: 9, partner: 'bob', created_at: 'x' }, { status: 201 });
      }
    });
    render(InviteAccept, { token: 'T' });
    await userEvent.click(await screen.findByRole('button', { name: 'Accept' }));
    expect(seen).toContain('POST /comparisons/invites/T/accept');
    await vi.waitFor(() => expect(goto).toHaveBeenCalledWith('/compare/9'));
  });

  it('says so when the invite is gone', async () => {
    stubFetch(() => new Response('{}', { status: 404 }));
    render(InviteAccept, { token: 'T' });
    expect(await screen.findByText(/no longer valid/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Accept' })).toBeNull();
  });

  it('does not offer to accept your own invite', async () => {
    stubFetch(() => Response.json({ inviter: 'alice', own: true }));
    render(InviteAccept, { token: 'T' });
    expect(await screen.findByText(/your own invite link/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Accept' })).toBeNull();
  });

  it('explains a refusal because the two already compare', async () => {
    stubFetch((m, url) => url.endsWith('/accept')
      ? new Response('{}', { status: 409 })
      : Response.json({ inviter: 'bob', own: false }));
    render(InviteAccept, { token: 'T' });
    await userEvent.click(await screen.findByRole('button', { name: 'Accept' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('You already compare with bob.');
  });
});
