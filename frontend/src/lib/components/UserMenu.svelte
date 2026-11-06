<script lang="ts">
  import { api } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatRelative } from '$lib/format';

  let open = $state(false);
  let busy = $state(false);
  let root: HTMLDivElement | undefined = $state();

  const user = $derived($auth.user);
  const zones = $derived.by(() => {
    const all = new Set<string>(
      typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
    );
    all.add('UTC');
    if (user?.timezone) all.add(user.timezone);
    return [...all].sort();
  });
  const syncText = $derived(
    user?.last_synced_at ? `Synced ${formatRelative(user.last_synced_at, new Date())}` : 'Importing your history…'
  );

  function onWindowClick(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
  function onWindowKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') open = false;
  }

  async function changeTimezone(e: Event) {
    const timezone = (e.currentTarget as HTMLSelectElement).value;
    busy = true;
    try {
      const updated = await api.updateMe({ timezone });
      auth.update((s) => ({ ...s, user: updated }));
    } finally {
      busy = false;
    }
  }

  async function logout() {
    await api.logout();
    auth.set({ user: null, loading: false });
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

{#if user}
  <div class="menu" bind:this={root}>
    <button
      type="button"
      aria-expanded={open}
      aria-controls="user-menu-panel"
      onclick={() => (open = !open)}
    >{user.username}</button>
    {#if open}
      <div class="panel" id="user-menu-panel">
        <p class="sync">{syncText}</p>
        <label>
          <span>Timezone</span>
          <select value={user.timezone ?? 'UTC'} onchange={changeTimezone} disabled={busy}>
            {#each zones as zone (zone)}
              <option value={zone}>{zone}</option>
            {/each}
          </select>
        </label>
        <button type="button" class="ghost" onclick={logout}>Log out</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .menu {
    position: relative;
  }
  .panel {
    position: absolute;
    right: 0;
    top: calc(100% + 0.4rem);
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 15rem;
    padding: 0.85rem;
    background: var(--surface0);
    border-radius: var(--r-sm);
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
  }
  .sync {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.82rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  select {
    background: var(--surface1);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.35rem 0.5rem;
    font-size: 0.82rem;
  }
  select:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  button {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    font-size: 0.82rem;
    cursor: pointer;
    transition: box-shadow var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out);
  }
  button:hover:not(:disabled) {
    background: var(--surface1);
  }
  button:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .panel button {
    background: var(--surface1);
  }
  .panel button:hover {
    background: var(--surface2, var(--surface1));
  }
  .ghost {
    color: var(--text-muted);
  }
</style>
