import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { mockApi } from '$lib/test/mockApi';
import { config, loadConfig } from './config';

describe('config store', () => {
  beforeEach(() => config.set({ linkhopUrl: null }));

  it('reads the linkhop URL from the public config endpoint', async () => {
    const { calls } = mockApi({ '/auth/config': { linkhop_url: 'https://linkhop.example' } });
    await loadConfig();
    expect(calls).toEqual(['/auth/config']);
    expect(get(config).linkhopUrl).toBe('https://linkhop.example');
  });

  it('has no linkhop URL when none is configured', async () => {
    mockApi({ '/auth/config': { linkhop_url: null } });
    await loadConfig();
    expect(get(config).linkhopUrl).toBeNull();
  });

  it('stays without one when the endpoint fails', async () => {
    mockApi({});
    await loadConfig();
    expect(get(config).linkhopUrl).toBeNull();
  });
});
