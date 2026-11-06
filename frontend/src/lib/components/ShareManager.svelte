<!-- frontend/src/lib/components/ShareManager.svelte -->
<script lang="ts">
  import { api, type Share, type ShareCreate } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { range, rangeLabel, toParams } from '$lib/stores/range';

  let open = $state(false);
  let busy = $state(false);
  let loaded = $state(false);
  let shares = $state<Share[]>([]);
  let error = $state<string | null>(null);
  let label = $state('');
  let scope = $state<'all' | 'current'>('all');
  let root: HTMLDivElement | undefined = $state();

  const tz = $derived($auth.user?.timezone ?? 'UTC');
  const isAll = $derived($range.kind === 'rolling' && $range.key === 'all');
  const currentLabel = $derived(rangeLabel($range));
  const effectiveScope = $derived(isAll ? 'all' : scope);

  $effect(() => {
    if (isAll) scope = 'all';
  });

  function localDay(ms: number): string {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date(ms));
  }

  function rangeText(s: Share): string {
    const from = s.range_from ? localDay(Date.parse(s.range_from)) : null;
    const to = s.range_to ? localDay(Date.parse(s.range_to) - 1) : null;
    if (from && to) return `${from} – ${to}`;
    if (from) return `since ${from}`;
    if (to) return `until ${to}`;
    return 'All time';
  }

  const url = (s: Share) => `${location.origin}/s/${s.share_token}`;

  async function load() {
    error = null;
    try {
      shares = await api.listShares();
      loaded = true;
    } catch {
      error = 'Could not load share links.';
    }
  }

  function toggle() {
    open = !open;
    if (open) void load();
  }

  function onWindowClick(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
  function onWindowKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') open = false;
  }

  function buildBody(): ShareCreate {
    const body: ShareCreate = {};
    const text = label.trim();
    if (text) body.label = text;
    if (effectiveScope === 'current') {
      const now = new Date();
      const p = toParams($range, tz, now);
      if (p.since) {
        body.range_from = p.since;
        body.range_to = now.toISOString();
      } else {
        if (p.start) body.start = p.start;
        if (p.end) body.end = p.end;
      }
    }
    return body;
  }

  async function create(e: Event) {
    e.preventDefault();
    busy = true;
    error = null;
    try {
      const created = await api.createShare(buildBody());
      shares = [created, ...shares];
      label = '';
    } catch {
      error = 'Could not create the link.';
    } finally {
      busy = false;
    }
  }

  async function revoke(s: Share) {
    error = null;
    try {
      await api.revokeShare(s.share_token);
      shares = shares.filter((x) => x.share_token !== s.share_token);
    } catch {
      error = 'Could not revoke the link.';
    }
  }

  async function copy(s: Share) {
    try {
      await navigator.clipboard.writeText(url(s));
    } catch {
      error = 'Could not copy the link.';
    }
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<div class="share" bind:this={root}>
  <button type="button" aria-expanded={open} aria-controls="share-panel" onclick={toggle}>Share</button>
  {#if open}
    <div class="panel" id="share-panel">
      {#if loaded && shares.length === 0}
        <p class="muted">No active links</p>
      {/if}
      {#if shares.length > 0}
        <ul>
          {#each shares as s (s.share_token)}
            <li>
              <div class="info">
                <span class="name">{s.label ?? 'Untitled'}</span>
                <span class="range">{rangeText(s)}</span>
                <span class="link">{url(s)}</span>
              </div>
              <button type="button" onclick={() => copy(s)}>Copy</button>
              <button type="button" class="ghost" onclick={() => revoke(s)}>Revoke</button>
            </li>
          {/each}
        </ul>
      {/if}
      <form onsubmit={create}>
        <label>
          <span>Label</span>
          <input type="text" bind:value={label} maxlength="100" />
        </label>
        <fieldset>
          <label class="choice">
            <input type="radio" name="share-scope" value="all" bind:group={scope} />
            All time
          </label>
          {#if !isAll}
            <label class="choice">
              <input type="radio" name="share-scope" value="current" bind:group={scope} />
              Current range ({currentLabel})
            </label>
          {/if}
        </fieldset>
        <button type="submit" disabled={busy}>Create</button>
      </form>
      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .share {
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
    width: 22rem;
    max-width: calc(100vw - 2rem);
    padding: 0.85rem;
    background: var(--surface0);
    border-radius: var(--r-sm);
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    font-size: 0.82rem;
  }
  .range,
  .muted {
    color: var(--text-muted);
    font-size: 0.78rem;
  }
  .muted {
    margin: 0;
  }
  .link {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.72rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  fieldset {
    border: 0;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .choice {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
    color: var(--text);
  }
  input[type='text'] {
    background: var(--surface1);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.35rem 0.5rem;
    font-size: 0.82rem;
  }
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.78rem;
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
  .panel button {
    background: var(--surface1);
  }
  button:hover:not(:disabled) {
    background: var(--surface1);
  }
  button:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  button:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .ghost {
    color: var(--text-muted);
  }
</style>
