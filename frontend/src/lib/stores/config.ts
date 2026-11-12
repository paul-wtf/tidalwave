import { writable } from 'svelte/store';
import { api } from '$lib/api/client';

export interface AppConfig { linkhopUrl: string | null; }

/** What the backend is configured with. The static build cannot know it. */
export const config = writable<AppConfig>({ linkhopUrl: null });

export async function loadConfig(): Promise<void> {
  try {
    const { linkhop_url } = await api.config();
    config.set({ linkhopUrl: linkhop_url || null });
  } catch {
    // the pages work without it; only the linkhop link is missing
  }
}
