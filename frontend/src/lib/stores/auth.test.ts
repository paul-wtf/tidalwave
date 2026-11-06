import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { auth, loadMe } from './auth';
import { api } from '$lib/api/client';

const ME = {
  username: 'alice', is_admin: true, timezone: null, disconnected: false,
  last_synced_at: null, last_played_at: null
};

describe('auth store', () => {
  beforeEach(() => { auth.set({ user: null, loading: false }); });

  it('loadMe populates the user when logged in', async () => {
    vi.spyOn(api, 'me').mockResolvedValue(ME);
    await loadMe();
    expect(get(auth).user).toEqual(ME);
    expect(get(auth).loading).toBe(false);
  });

  it('loadMe leaves user null when anonymous', async () => {
    vi.spyOn(api, 'me').mockResolvedValue(null);
    await loadMe();
    expect(get(auth).user).toBeNull();
  });
});

describe('loadMe timezone sync', () => {
  it('stores the browser timezone once when the profile has none', async () => {
    vi.spyOn(api, 'me').mockResolvedValue(ME);
    const update = vi.spyOn(api, 'updateMe').mockResolvedValue({ ...ME, timezone: 'Europe/Berlin' });
    await loadMe();
    expect(update).toHaveBeenCalledWith({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
    expect(get(auth).user?.timezone).toBe('Europe/Berlin');
  });

  it('does not update when a timezone is set', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ ...ME, timezone: 'UTC' });
    const update = vi.spyOn(api, 'updateMe').mockResolvedValue(ME);
    update.mockClear();
    await loadMe();
    expect(update).not.toHaveBeenCalled();
  });
});
