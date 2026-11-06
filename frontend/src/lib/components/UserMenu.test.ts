import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { get } from 'svelte/store';
import UserMenu from './UserMenu.svelte';
import { auth } from '$lib/stores/auth';
import { mockApi } from '$lib/test/mockApi';
import type { Me } from '$lib/api/client';

const me = (over: Partial<Me> = {}): Me => ({
  username: 'paul', is_admin: false, timezone: 'UTC', disconnected: false,
  last_synced_at: null, last_played_at: null, ...over
});

afterEach(() => vi.useRealTimers());

describe('UserMenu', () => {
  it('shows the import state when nothing has synced yet', async () => {
    auth.set({ user: me(), loading: false });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    expect(screen.getByText('Importing your history…')).toBeInTheDocument();
  });

  it('shows the relative sync time', async () => {
    auth.set({ user: me({ last_synced_at: new Date(Date.now() - 3 * 60_000).toISOString() }), loading: false });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    expect(screen.getByText('Synced 3 min ago')).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    auth.set({ user: me(), loading: false });
    render(UserMenu);
    const btn = screen.getByRole('button', { name: /paul/ });
    await userEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
    await userEvent.keyboard('{Escape}');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
  });

  it('patches the timezone and updates the store', async () => {
    auth.set({ user: me(), loading: false });
    const { requests } = mockApi({ '/auth/me': me({ timezone: 'Europe/Berlin' }) });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.selectOptions(screen.getByLabelText('Timezone'), 'Europe/Berlin');
    expect(requests).toContainEqual({ method: 'PATCH', url: '/auth/me' });
    await vi.waitFor(() => expect(get(auth).user?.timezone).toBe('Europe/Berlin'));
  });

  it('logs out and clears the user', async () => {
    auth.set({ user: me(), loading: false });
    const { requests } = mockApi({});
    vi.stubGlobal('fetch', vi.fn(async (u: string, init?: RequestInit) => {
      requests.push({ method: init?.method ?? 'GET', url: String(u) });
      return new Response(null, { status: 204 });
    }));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }));
    expect(requests).toContainEqual({ method: 'POST', url: '/auth/logout' });
    await vi.waitFor(() => expect(get(auth)).toEqual({ user: null, loading: false }));
  });
  it('resets the select and shows an alert when the timezone change fails', async () => {
    auth.set({ user: me(), loading: false });
    mockApi({});
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    const select = screen.getByLabelText('Timezone') as HTMLSelectElement;
    await userEvent.selectOptions(select, 'Europe/Berlin');
    expect(await screen.findByRole('alert')).toHaveTextContent(/timezone/i);
    expect(select.value).toBe('UTC');
    expect(get(auth).user?.timezone).toBe('UTC');
  });

  it('shows an alert and keeps the user when logout fails', async () => {
    auth.set({ user: me(), loading: false });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 500 })));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/log out/i);
    expect(get(auth).user?.username).toBe('paul');
  });
});
