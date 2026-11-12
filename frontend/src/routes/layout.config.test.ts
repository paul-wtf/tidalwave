import { render, waitFor } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { mockApi } from '$lib/test/mockApi';
import { config } from '$lib/stores/config';
import Layout from './+layout.svelte';

describe('root layout', () => {
  it('loads the public config once for every page under it', async () => {
    config.set({ linkhopUrl: null });
    const { calls } = mockApi({ '/auth/config': { linkhop_url: 'https://linkhop.example' } });
    render(Layout);
    await waitFor(() => expect(get(config).linkhopUrl).toBe('https://linkhop.example'));
    expect(calls).toEqual(['/auth/config']);
  });
});
