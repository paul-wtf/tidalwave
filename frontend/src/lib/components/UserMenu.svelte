<script lang="ts">
  import { api, ApiError } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatRelative } from '$lib/format';
  import { compactHeader, shareOpen } from '$lib/stores/header';
  import { theme, toggleTheme } from '$lib/stores/theme';

  let open = $state(false);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let root: HTMLDivElement | undefined = $state();
  let deleting = $state(false);
  let typed = $state('');
  let webhook = $state('');
  let report = $state<{ text: string; failed: boolean } | null>(null);

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
    // composedPath, because a button that swaps itself out is already detached
    // from root by the time this handler runs.
    if (open && root && !e.composedPath().includes(root)) open = false;
  }
  function onWindowKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') open = false;
  }

  async function changeTimezone(e: Event) {
    const select = e.currentTarget as HTMLSelectElement;
    busy = true;
    error = null;
    try {
      const updated = await api.updateMe({ timezone: select.value });
      auth.update((s) => ({ ...s, user: updated }));
    } catch {
      select.value = user?.timezone ?? 'UTC';
      error = 'Could not change the timezone.';
    } finally {
      busy = false;
    }
  }

  async function saveWebhook(e: Event) {
    e.preventDefault();
    busy = true;
    report = null;
    try {
      const updated = await api.setWebhook(webhook.trim());
      auth.update((s) => ({ ...s, user: updated }));
      webhook = '';
    } catch (err) {
      report = {
        failed: true,
        text: err instanceof ApiError && err.status === 422
          ? 'That is not a Discord webhook URL. It starts with https://discord.com/api/webhooks/.'
          : 'Could not save the webhook.'
      };
    } finally {
      busy = false;
    }
  }

  async function sendTest() {
    busy = true;
    report = null;
    try {
      await api.testWebhook();
      report = { failed: false, text: 'Test message sent.' };
    } catch {
      report = { failed: true, text: 'Discord did not take the test message.' };
    } finally {
      busy = false;
    }
  }

  async function removeWebhook() {
    busy = true;
    report = null;
    try {
      const updated = await api.clearWebhook();
      auth.update((s) => ({ ...s, user: updated }));
    } catch {
      report = { failed: true, text: 'Could not remove the webhook.' };
    } finally {
      busy = false;
    }
  }

  function closeDeletion() {
    deleting = false;
    typed = '';
  }

  $effect(() => {
    if (!open) closeDeletion();
  });

  async function deleteAccount(e: Event) {
    e.preventDefault();
    if (typed !== user?.username) return;
    busy = true;
    error = null;
    try {
      await api.deleteAccount();
      auth.set({ user: null, loading: false });
    } catch {
      error = 'Could not delete the account.';
    } finally {
      busy = false;
    }
  }

  function openShares(e: MouseEvent) {
    e.stopPropagation();
    open = false;
    shareOpen.set(true);
  }

  async function logout() {
    error = null;
    try {
      await api.logout();
      auth.set({ user: null, loading: false });
    } catch {
      error = 'Could not log out.';
    }
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

{#if user}
  <div class="menu" bind:this={root}>
    <button
      type="button"
      class:compact={$compactHeader}
      title={$compactHeader ? undefined : user.username}
      aria-expanded={open}
      aria-controls="user-menu-panel"
      onclick={() => (open = !open)}
    >
      {#if $compactHeader}
        <span aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
        <span class="sr-only">{user.username}</span>
      {:else}
        {user.username}
      {/if}
    </button>
    {#if open}
      <div class="panel" id="user-menu-panel">
        <p class="sync">{syncText}</p>
        {#if $compactHeader}
          <div class="row">
            <button type="button" onclick={openShares}>Share links</button>
            <button type="button" onclick={toggleTheme}>
              Switch to {$theme === 'mocha' ? 'Latte' : 'Mocha'}
            </button>
          </div>
        {/if}
        <label>
          <span>Timezone</span>
          <select value={user.timezone ?? 'UTC'} onchange={changeTimezone} disabled={busy}>
            {#each zones as zone (zone)}
              <option value={zone}>{zone}</option>
            {/each}
          </select>
        </label>
        <div class="export">
          <span>Your listens</span>
          <a href="/spellings" onclick={() => (open = false)}>Spellings</a>
          <a href="/import" onclick={() => (open = false)}>Import</a>
        </div>
        <div class="export">
          <span>Export my data</span>
          <a href={api.exportUrl('csv')} download>CSV</a>
          <a href={api.exportUrl('json')} download>JSON</a>
          <a href={api.exportUrl('csv', 'merges')} download>Merges CSV</a>
        </div>
        <div class="report">
          <span class="heading">Weekly report on Discord</span>
          {#if user.weekly_report_webhook}
            <span class="hook">{user.weekly_report_webhook}</span>
            <div class="row">
              <button type="button" onclick={sendTest} disabled={busy}>Send test</button>
              <button type="button" class="ghost" onclick={removeWebhook} disabled={busy}>Remove</button>
            </div>
          {:else}
            <form onsubmit={saveWebhook}>
              <label>
                <span>Discord webhook URL</span>
                <input
                  type="url"
                  bind:value={webhook}
                  placeholder="https://discord.com/api/webhooks/…"
                  autocomplete="off"
                  spellcheck="false"
                />
              </label>
              <button type="submit" disabled={busy || !webhook.trim()}>Save</button>
            </form>
            <p class="hint">Every Monday morning, a summary of last week goes to this channel.</p>
          {/if}
          {#if report}
            <p class={report.failed ? 'error' : 'ok'} role={report.failed ? 'alert' : 'status'}>
              {report.text}
            </p>
          {/if}
        </div>
        <button type="button" class="ghost" onclick={logout}>Log out</button>
        {#if deleting}
          <form class="danger" onsubmit={deleteAccount}>
            <p>
              This deletes your tidalwave account with all your listens, your share links, your
              comparisons and your sync state. It cannot be undone. Your Last.fm account stays as
              it is.
            </p>
            <label>
              <span>Type {user.username} to confirm</span>
              <input type="text" bind:value={typed} autocomplete="off" spellcheck="false" />
            </label>
            <div class="row">
              <button type="button" onclick={closeDeletion}>Cancel</button>
              <button type="submit" class="destroy" disabled={busy || typed !== user.username}>
                Delete account for good
              </button>
            </div>
          </form>
        {:else}
          <button type="button" class="ghost" onclick={() => (deleting = true)}>
            Delete account
          </button>
        {/if}
        {#if error}
          <p class="error" role="alert">{error}</p>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .menu {
    position: relative;
  }
  .panel {
    position: fixed;
    top: var(--bar-h);
    right: clamp(1rem, 4vw, 2rem);
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    width: 19rem;
    max-width: calc(100vw - 2rem);
    max-height: calc(100dvh - var(--bar-h) - 1rem);
    overflow-y: auto;
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
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.78rem;
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
  select:focus-visible,
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  input {
    background: var(--surface1);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.35rem 0.5rem;
    font-size: 0.82rem;
  }
  .report {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.82rem;
  }
  .report form {
    display: flex;
    align-items: flex-end;
    gap: 0.4rem;
  }
  .report label {
    flex: 1;
    min-width: 0;
  }
  .hook {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }
  .hint {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .ok {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.78rem;
  }
  .export {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
  }
  .export span {
    flex: 1;
  }
  .export a {
    padding: 0.4rem 0.85rem;
    border-radius: var(--r-sm);
    background: var(--surface1);
    color: var(--text);
    text-decoration: none;
  }
  .export a:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .danger {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.7rem;
    border-radius: var(--r-sm);
    background: var(--error-soft);
  }
  .danger p {
    margin: 0;
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .danger label {
    color: var(--text);
  }
  .row {
    display: flex;
    gap: 0.4rem;
  }
  .row .destroy {
    flex: 1;
  }
  .panel .destroy,
  .panel .destroy:hover {
    background: var(--error);
    color: var(--accent-contrast);
  }
  button:disabled {
    opacity: 0.55;
    cursor: default;
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
  .menu > button:not(.compact) {
    max-width: 9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .compact {
    width: 2.2rem;
    height: 2.2rem;
    padding: 0;
    border-radius: 50%;
    font-family: var(--font-display);
    font-weight: 700;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
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
