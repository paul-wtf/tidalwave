import { describe, it, expect, afterEach, vi } from 'vitest';
import { api, statsApi } from './client';
import { mockApi } from '$lib/test/mockApi';

const ME = {
  username: 'alice', is_admin: true, timezone: 'Europe/Berlin', disconnected: false,
  last_synced_at: null, last_played_at: null
};

describe('api client', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('me() returns the user and sends credentials', async () => {
    const { calls } = mockApi({ '/auth/me': ME });
    expect(await api.me()).toEqual(ME);
    expect(calls).toEqual(['/auth/me']);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/auth/me', expect.objectContaining({ credentials: 'include' }));
  });

  it('me() returns null on 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));
    expect(await api.me()).toBeNull();
  });

  it('updateMe() patches the timezone', async () => {
    mockApi({ '/auth/me': ME });
    await api.updateMe({ timezone: 'Europe/Berlin' });
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/auth/me', expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ timezone: 'Europe/Berlin' })
    }));
  });

  it('createShare() posts the body and returns the share', async () => {
    mockApi({ '/shares': { share_token: 'TOK' } });
    expect(await api.createShare({ label: 'x', start: '2026-01-01' })).toEqual({ share_token: 'TOK' });
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/shares', expect.objectContaining({
      method: 'POST', credentials: 'include', body: JSON.stringify({ label: 'x', start: '2026-01-01' })
    }));
  });
});

describe('statsApi', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('own mode hits /stats with the limit and range params', async () => {
    const { calls } = mockApi({ '/stats/top-artists': [{ artist: 'A', count: 3, image_url: null }] });
    const rows = await statsApi().topArtists(5, { since: '2026-01-01T00:00:00Z' });
    expect(rows[0].artist).toBe('A');
    expect(calls).toEqual(['/stats/top-artists?limit=5&since=2026-01-01T00%3A00%3A00Z']);
  });

  it('shared mode hits /shared/<token>', async () => {
    const { calls } = mockApi({ '/shared/TOK/clock': [1] });
    await statsApi('TOK').clock({});
    expect(calls).toEqual(['/shared/TOK/clock']);
  });

  it('summary(compare) adds compare=true and calendar', async () => {
    const { calls } = mockApi({ '/stats/summary': {} });
    await statsApi().summary({ start: '2026-03-01', calendar: 'month' }, true);
    expect(calls).toEqual(['/stats/summary?start=2026-03-01&calendar=month&compare=true']);
  });

  it('detail calls encode names exactly', async () => {
    const { calls } = mockApi({ '/stats/track': {} });
    await statsApi().track('AC/DC & Co', 'Who? #1', {});
    expect(calls).toEqual(['/stats/track?artist=AC%2FDC+%26+Co&track=Who%3F+%231']);
  });

  it('throws ApiError on 404', async () => {
    mockApi({});
    await expect(statsApi('TOK').topArtists(5, {})).rejects.toThrow();
  });

});

describe('api client: admin, comparisons and reports', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('admin calls go to /auth/admin', async () => {
    const { requests, bodies } = mockApi({
      '/auth/admin/users': [], '/auth/admin/allowlist': { mode: 'allowlist', entries: [] },
      'POST /auth/admin/allowlist': { username: 'carol', fixed: false, added_at: 'x' },
      'DELETE /auth/admin/users/7': null, 'DELETE /auth/admin/allowlist/a%2Fb': null
    });
    await api.adminUsers();
    await api.allowlist();
    expect(await api.addToAllowlist('carol')).toEqual({ username: 'carol', fixed: false, added_at: 'x' });
    await api.deleteUser(7);
    await api.removeFromAllowlist('a/b');
    expect(requests).toEqual([
      { method: 'GET', url: '/auth/admin/users' },
      { method: 'GET', url: '/auth/admin/allowlist' },
      { method: 'POST', url: '/auth/admin/allowlist' },
      { method: 'DELETE', url: '/auth/admin/users/7' },
      { method: 'DELETE', url: '/auth/admin/allowlist/a%2Fb' }
    ]);
    expect(bodies['POST /auth/admin/allowlist']).toBe(JSON.stringify({ username: 'carol' }));
  });

  it('comparison calls go to /comparisons with the range', async () => {
    const { requests } = mockApi({
      '/comparisons': { pairs: [], invites: [] },
      'POST /comparisons/invites': { token: 'T' },
      '/comparisons/invites/T': { inviter: 'bob', own: false },
      'POST /comparisons/invites/T/accept': { id: 3 },
      'DELETE /comparisons/invites/T': null,
      '/comparisons/3': { id: 3 },
      'DELETE /comparisons/3': null
    });
    await api.comparisons();
    await api.createInvite();
    expect(await api.invite('T')).toEqual({ inviter: 'bob', own: false });
    await api.acceptInvite('T');
    await api.revokeInvite('T');
    await api.comparison(3, { since: '2026-11-01T00:00:00.000Z' });
    await api.endComparison(3);
    expect(requests.map((r) => `${r.method} ${r.url}`)).toEqual([
      'GET /comparisons',
      'POST /comparisons/invites',
      'GET /comparisons/invites/T',
      'POST /comparisons/invites/T/accept',
      'DELETE /comparisons/invites/T',
      'GET /comparisons/3?since=2026-11-01T00%3A00%3A00.000Z',
      'DELETE /comparisons/3'
    ]);
  });

  it('webhook calls go to /auth/me/webhook', async () => {
    const { requests, bodies } = mockApi({
      'PUT /auth/me/webhook': ME, 'DELETE /auth/me/webhook': ME, 'POST /auth/me/webhook/test': null
    });
    expect(await api.setWebhook('https://discord.com/api/webhooks/1/t')).toEqual(ME);
    expect(await api.clearWebhook()).toEqual(ME);
    await api.testWebhook();
    expect(requests.map((r) => `${r.method} ${r.url}`)).toEqual([
      'PUT /auth/me/webhook', 'DELETE /auth/me/webhook', 'POST /auth/me/webhook/test'
    ]);
    expect(bodies['PUT /auth/me/webhook']).toBe(JSON.stringify({ url: 'https://discord.com/api/webhooks/1/t' }));
  });

  it('a refused call carries its status', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 409 })));
    await expect(api.acceptInvite('T')).rejects.toMatchObject({ status: 409 });
    await expect(api.removeFromAllowlist('x')).rejects.toMatchObject({ status: 409 });
  });
});
