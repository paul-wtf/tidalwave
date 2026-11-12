import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import AdminPage from './AdminPage.svelte';
import { auth } from '$lib/stores/auth';
import type { AdminUser, Allowlist } from '$lib/api/client';
import { stubFetch, type Handler } from '$lib/test/stubFetch';

const users: AdminUser[] = [
  { id: 1, username: 'paul', is_admin: true, disconnected: false, created_at: '2026-06-17T10:00:00Z',
    listens: 12345, last_synced_at: new Date(Date.now() - 4 * 60_000).toISOString() },
  { id: 2, username: 'bob', is_admin: false, disconnected: true, created_at: '2026-10-01T10:00:00Z',
    listens: 0, last_synced_at: null }
];
const allowlist: Allowlist = {
  mode: 'allowlist',
  entries: [
    { username: 'carol', fixed: false, added_at: '2026-11-01T00:00:00Z' },
    { username: 'Dave', fixed: true, added_at: null }
  ]
};

function stub(handler: Handler) {
  return stubFetch((method, url, body) => {
    const res = handler(method, url, body);
    if (res) return res;
    if (url === '/auth/admin/users') return Response.json(users);
    if (url === '/auth/admin/allowlist' && method === 'GET') return Response.json(allowlist);
  });
}

describe('AdminPage', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'paul', is_admin: true, timezone: 'UTC' } as never, loading: false });
  });

  it('lists users with listens, last poll and their role', async () => {
    stub(() => undefined);
    render(AdminPage);
    const paul = await screen.findByRole('listitem', { name: 'paul' });
    expect(paul).toHaveTextContent('12,345 listens');
    expect(paul).toHaveTextContent('Polled 4 min ago');
    expect(paul).toHaveTextContent('admin');
    const bob = screen.getByRole('listitem', { name: 'bob' });
    expect(bob).toHaveTextContent('Never polled');
    expect(bob).toHaveTextContent('disconnected');
  });

  it('offers no delete button for yourself', async () => {
    stub(() => undefined);
    render(AdminPage);
    const paul = await screen.findByRole('listitem', { name: 'paul' });
    expect(within(paul).queryByRole('button', { name: /delete/i })).toBeNull();
    expect(within(screen.getByRole('listitem', { name: 'bob' }))
      .getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  it('deletes a user only after the name is typed', async () => {
    const seen = stub(() => undefined);
    render(AdminPage);
    const bob = await screen.findByRole('listitem', { name: 'bob' });
    await userEvent.click(within(bob).getByRole('button', { name: 'Delete' }));
    const confirm = within(bob).getByRole('button', { name: 'Delete bob for good' });
    expect(confirm).toBeDisabled();
    expect(bob).toHaveTextContent(/cannot be undone/);
    await userEvent.type(within(bob).getByLabelText('Type bob to confirm'), 'bob');
    await userEvent.click(confirm);
    expect(seen).toContain('DELETE /auth/admin/users/2');
    await vi.waitFor(() => expect(screen.queryByRole('listitem', { name: 'bob' })).toBeNull());
  });

  it('cancelling the deletion sends nothing', async () => {
    const seen = stub(() => undefined);
    render(AdminPage);
    const bob = await screen.findByRole('listitem', { name: 'bob' });
    await userEvent.click(within(bob).getByRole('button', { name: 'Delete' }));
    await userEvent.click(within(bob).getByRole('button', { name: 'Cancel' }));
    expect(within(bob).queryByLabelText('Type bob to confirm')).toBeNull();
    expect(seen.filter((s) => s.startsWith('DELETE'))).toEqual([]);
  });

  it('shows environment entries as fixed and the others as removable', async () => {
    const seen = stub(() => undefined);
    render(AdminPage);
    const dave = await screen.findByRole('listitem', { name: 'Dave' });
    expect(dave).toHaveTextContent('from TIDALWAVE_REGISTRATION_ALLOWLIST');
    expect(within(dave).queryByRole('button')).toBeNull();
    const carol = screen.getByRole('listitem', { name: 'carol' });
    await userEvent.click(within(carol).getByRole('button', { name: 'Remove' }));
    expect(seen).toContain('DELETE /auth/admin/allowlist/carol');
    await vi.waitFor(() => expect(screen.queryByRole('listitem', { name: 'carol' })).toBeNull());
  });

  it('adds a name to the allowlist', async () => {
    const seen = stub((method, url, body) =>
      method === 'POST' && url === '/auth/admin/allowlist'
        ? Response.json({ username: JSON.parse(body!).username, fixed: false, added_at: '2026-11-12T00:00:00Z' }, { status: 201 })
        : undefined
    );
    render(AdminPage);
    await screen.findByRole('listitem', { name: 'Dave' });
    await userEvent.type(screen.getByLabelText('Last.fm username'), 'erin');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(seen).toContain('POST /auth/admin/allowlist');
    expect(await screen.findByRole('listitem', { name: 'erin' })).toBeInTheDocument();
    expect(screen.getByLabelText('Last.fm username')).toHaveValue('');
  });

  it('says when a name is already listed', async () => {
    stub((method) => (method === 'POST' ? new Response('{}', { status: 409 }) : undefined));
    render(AdminPage);
    await screen.findByRole('listitem', { name: 'Dave' });
    await userEvent.type(screen.getByLabelText('Last.fm username'), 'dave');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('dave is already on the allowlist.');
  });

  it('explains that the allowlist does nothing in open mode', async () => {
    stub((method, url) =>
      url === '/auth/admin/allowlist' && method === 'GET'
        ? Response.json({ mode: 'open', entries: [] })
        : undefined
    );
    render(AdminPage);
    expect(await screen.findByText(/Registration is open/)).toBeInTheDocument();
  });

  it('tells non-admins this page is not for them', async () => {
    stub(() => new Response('{}', { status: 403 }));
    render(AdminPage);
    expect(await screen.findByText('Only admins can see this page.')).toBeInTheDocument();
  });
});
