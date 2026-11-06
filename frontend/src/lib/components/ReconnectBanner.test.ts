import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ReconnectBanner from './ReconnectBanner.svelte';
import { auth } from '$lib/stores/auth';
import type { Me } from '$lib/api/client';

const me = (disconnected: boolean): Me => ({
  username: 'paul', is_admin: false, timezone: 'UTC', disconnected,
  last_synced_at: null, last_played_at: null
});

describe('ReconnectBanner', () => {
  it('renders when the Last.fm link is revoked', () => {
    auth.set({ user: me(true), loading: false });
    render(ReconnectBanner);
    expect(screen.getByText(/Last\.fm access was revoked/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Reconnect' })).toHaveAttribute('href', '/auth/login');
  });

  it('renders nothing when connected', () => {
    auth.set({ user: me(false), loading: false });
    render(ReconnectBanner);
    expect(screen.queryByText(/revoked/)).toBeNull();
  });

  it('renders nothing without a user', () => {
    auth.set({ user: null, loading: false });
    render(ReconnectBanner);
    expect(screen.queryByText(/revoked/)).toBeNull();
  });
});
