import { writable } from 'svelte/store';
import { api, type Me } from '$lib/api/client';

export interface AuthState { user: Me | null; loading: boolean; }

export const auth = writable<AuthState>({ user: null, loading: true });

export async function loadMe(): Promise<void> {
  auth.update((s) => ({ ...s, loading: true }));
  const user = await api.me();
  auth.set({ user, loading: false });
}
