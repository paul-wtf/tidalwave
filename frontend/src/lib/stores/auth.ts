import { writable } from 'svelte/store';
import { api, type Me } from '$lib/api/client';

export interface AuthState { user: Me | null; loading: boolean; }

export const auth = writable<AuthState>({ user: null, loading: true });

export async function loadMe(): Promise<void> {
  auth.update((s) => ({ ...s, loading: true }));
  let user = await api.me();
  if (user && user.timezone == null) {
    try {
      user = await api.updateMe({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
    } catch {
      // the backend treats a missing timezone as UTC
    }
  }
  auth.set({ user, loading: false });
}
