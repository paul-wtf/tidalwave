import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { get } from 'svelte/store';
import UserMenu from './UserMenu.svelte';
import { auth } from '$lib/stores/auth';
import { mockApi } from '$lib/test/mockApi';
import type { Me } from '$lib/api/client';
import { stubFetch } from '$lib/test/stubFetch';

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

  it('links to the CSV and JSON export', async () => {
    auth.set({ user: me(), loading: false });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    expect(screen.getByText('Export my data')).toBeInTheDocument();
    const csv = screen.getByRole('link', { name: 'CSV' });
    expect(csv).toHaveAttribute('href', '/auth/export?format=csv');
    expect(csv).toHaveAttribute('download');
    expect(screen.getByRole('link', { name: 'JSON' })).toHaveAttribute('href', '/auth/export?format=json');
  });

  it('asks for the username before it deletes the account', async () => {
    auth.set({ user: me(), loading: false });
    const requests: { method: string; url: string }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: string, init?: RequestInit) => {
      requests.push({ method: init?.method ?? 'GET', url: String(u) });
      return new Response(null, { status: 204 });
    }));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    expect(screen.queryByLabelText(/Type paul to confirm/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));

    expect(screen.getByText(/all your listens, your share links, your comparisons and your sync state/)).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Delete account for good' });
    expect(confirm).toBeDisabled();
    const field = screen.getByLabelText(/Type paul to confirm/);
    await userEvent.type(field, 'Paul');
    expect(confirm).toBeDisabled();
    await userEvent.clear(field);
    await userEvent.type(field, 'paul');
    expect(confirm).toBeEnabled();
    expect(requests).toEqual([]);

    await userEvent.click(confirm);
    expect(requests).toEqual([{ method: 'DELETE', url: '/auth/me' }]);
    await vi.waitFor(() => expect(get(auth)).toEqual({ user: null, loading: false }));
  });

  it('backs out of the deletion with Cancel', async () => {
    auth.set({ user: me(), loading: false });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
    await userEvent.type(screen.getByLabelText(/Type paul to confirm/), 'paul');
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByLabelText(/Type paul to confirm/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
    expect(screen.getByLabelText(/Type paul to confirm/)).toHaveValue('');
  });

  it('keeps the user and shows an alert when the deletion fails', async () => {
    auth.set({ user: me(), loading: false });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 500 })));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
    await userEvent.type(screen.getByLabelText(/Type paul to confirm/), 'paul');
    await userEvent.click(screen.getByRole('button', { name: 'Delete account for good' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/delete/i);
    expect(get(auth).user?.username).toBe('paul');
  });

  it('saves a Discord webhook and then shows it only masked', async () => {
    auth.set({ user: me(), loading: false });
    const masked = 'https://discord.com/api/webhooks/1234…/…wxyz';
    const seen = stubFetch((m, url, body) => {
      if (m === 'PUT' && url === '/auth/me/webhook') {
        expect(JSON.parse(body!)).toEqual({ url: 'https://discord.com/api/webhooks/123456/secretwxyz' });
        return Response.json(me({ weekly_report_webhook: masked }));
      }
    });
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.type(screen.getByLabelText('Discord webhook URL'), 'https://discord.com/api/webhooks/123456/secretwxyz');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(seen).toContain('PUT /auth/me/webhook');
    expect(await screen.findByText(masked)).toBeInTheDocument();
    expect(screen.queryByLabelText('Discord webhook URL')).toBeNull();
    expect(get(auth).user?.weekly_report_webhook).toBe(masked);
  });

  it('says what a webhook URL must look like when the server refuses it', async () => {
    auth.set({ user: me(), loading: false });
    stubFetch(() => new Response('{}', { status: 422 }));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.type(screen.getByLabelText('Discord webhook URL'), 'https://example.com/hook');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('https://discord.com/api/webhooks/');
  });

  it('sends a test message and reports the outcome', async () => {
    auth.set({ user: me({ weekly_report_webhook: 'https://discord.com/api/webhooks/1234…/…wxyz' }), loading: false });
    let answer = 204;
    const seen = stubFetch(() => new Response(null, { status: answer }));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Send test' }));
    expect(seen).toContain('POST /auth/me/webhook/test');
    expect(await screen.findByRole('status')).toHaveTextContent('Test message sent.');
    answer = 502;
    await userEvent.click(screen.getByRole('button', { name: 'Send test' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Discord did not take the test message.');
  });

  it('removes the webhook', async () => {
    auth.set({ user: me({ weekly_report_webhook: 'https://discord.com/api/webhooks/1234…/…wxyz' }), loading: false });
    const seen = stubFetch((m) => (m === 'DELETE' ? Response.json(me({ weekly_report_webhook: null })) : undefined));
    render(UserMenu);
    await userEvent.click(screen.getByRole('button', { name: /paul/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(seen).toContain('DELETE /auth/me/webhook');
    expect(await screen.findByLabelText('Discord webhook URL')).toBeInTheDocument();
  });
});
