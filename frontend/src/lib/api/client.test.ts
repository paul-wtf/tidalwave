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
