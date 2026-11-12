<script lang="ts">
  import { goto } from '$app/navigation';
  import { statsApi, type SearchResults } from '$lib/api/client';
  import { rangeQuery } from '$lib/stores/range';
  import { artistHref, albumHref, trackHref } from '$lib/links';
  import Cover from './Cover.svelte';

  let { token }: { token?: string } = $props();

  const DEBOUNCE_MS = 200;

  type Entry = { label: string; sub?: string; count: number; href: string; image?: string | null };
  type Group = { title: string; covers: boolean; entries: Entry[] };

  let query = $state('');
  let results = $state<SearchResults | null>(null);
  let open = $state(false);
  let active = $state(0);
  let input: HTMLInputElement | undefined = $state();
  let root: HTMLDivElement | undefined = $state();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let latest = 0;

  const base = $derived(token ? `/s/${token}` : '');
  const groups = $derived.by((): Group[] => {
    if (!results) return [];
    return [
      {
        title: 'Artists', covers: true,
        entries: results.artists.map((a) => ({
          label: a.artist, count: a.count, href: artistHref(base, a.artist), image: a.image_url
        }))
      },
      {
        title: 'Albums', covers: true,
        entries: results.albums.map((a) => ({
          label: a.album, sub: a.artist, count: a.count,
          href: albumHref(base, a.artist, a.album), image: a.image_url
        }))
      },
      {
        title: 'Tracks', covers: false,
        entries: results.tracks.map((t) => ({
          label: t.track, sub: t.artist, count: t.count, href: trackHref(base, t.artist, t.track)
        }))
      }
    ].filter((g) => g.entries.length > 0);
  });
  const flat = $derived(groups.flatMap((g) => g.entries));
  const offsets = $derived(
    groups.map((_, i) => groups.slice(0, i).reduce((n, g) => n + g.entries.length, 0))
  );
  const showPanel = $derived(open && results !== null);

  function schedule() {
    clearTimeout(timer);
    const q = query.trim();
    const ticket = ++latest;
    if (!q) {
      results = null;
      return;
    }
    open = true;
    const params = token == null ? $rangeQuery.params : undefined;
    timer = setTimeout(async () => {
      try {
        const found = await statsApi(token).search(q, params);
        if (ticket !== latest) return;
        results = found;
        active = 0;
      } catch {
        if (ticket === latest) results = null;
      }
    }, DEBOUNCE_MS);
  }

  function close() {
    clearTimeout(timer);
    latest++;
    open = false;
    query = '';
    results = null;
    input?.blur();
  }

  function onInputKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      close();
    } else if (showPanel && flat.length > 0 && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      active = (active + (e.key === 'ArrowDown' ? 1 : flat.length - 1)) % flat.length;
    } else if (e.key === 'Enter' && showPanel && flat[active]) {
      e.preventDefault();
      const { href } = flat[active];
      close();
      void goto(href);
    }
  }

  function typingElsewhere(target: EventTarget | null): boolean {
    return (
      target instanceof HTMLElement &&
      (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
    );
  }

  function onWindowKey(e: KeyboardEvent) {
    const chord = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k';
    const slash = e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !typingElsewhere(e.target);
    if (chord || slash) {
      e.preventDefault();
      input?.focus();
    }
  }

  function onWindowClick(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
</script>

<svelte:window onkeydown={onWindowKey} onclick={onWindowClick} />

<div class="search" bind:this={root}>
  <input
    bind:this={input}
    bind:value={query}
    type="search"
    role="combobox"
    aria-label="Search"
    aria-expanded={showPanel}
    aria-controls="search-results"
    aria-autocomplete="list"
    aria-activedescendant={showPanel && flat[active] ? `search-option-${active}` : undefined}
    placeholder="Search"
    autocomplete="off"
    spellcheck="false"
    oninput={schedule}
    onfocus={() => (open = true)}
    onkeydown={onInputKey}
  />
  <kbd aria-hidden="true">/</kbd>
  {#if showPanel}
    <div class="panel" id="search-results" role="listbox" aria-label="Search results">
      {#each groups as group, g (group.title)}
        <div class="group" role="group" aria-label={group.title}>
          <p class="eyebrow">{group.title}</p>
          {#each group.entries as entry, i (entry.href)}
            {@const index = offsets[g] + i}
            <a
              id="search-option-{index}"
              role="option"
              aria-selected={index === active}
              href={entry.href}
              tabindex="-1"
              onclick={close}
              onmouseenter={() => (active = index)}
            >
              {#if group.covers}<Cover src={entry.image} alt="" size={28} />{/if}
              <span class="text">
                <span class="label">{entry.label}</span>
                {#if entry.sub}<span class="sub">{entry.sub}</span>{/if}
              </span>
              {#if entry.count > 0}<span class="count">{entry.count}</span>{/if}
            </a>
          {/each}
        </div>
      {:else}
        <p class="none">No matches</p>
      {/each}
    </div>
  {/if}
</div>

<style>
  .search {
    position: relative;
    display: flex;
    align-items: center;
  }
  input {
    width: 11rem;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    padding: 0.38rem 1.7rem 0.38rem 0.65rem;
    border: 0;
    border-radius: var(--r-xs);
    background: var(--surface0);
    color: var(--text);
  }
  input::placeholder {
    color: var(--text-muted);
  }
  input::-webkit-search-cancel-button {
    display: none;
  }
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  kbd {
    position: absolute;
    right: 0.45rem;
    font-family: var(--font-mono);
    font-size: 0.68rem;
    line-height: 1;
    padding: 0.15rem 0.3rem;
    border-radius: 4px;
    background: var(--surface1);
    color: var(--text-muted);
    pointer-events: none;
  }
  input:focus + kbd {
    display: none;
  }
  .panel {
    position: fixed;
    top: var(--bar-h);
    right: clamp(1rem, 4vw, 2rem);
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    width: 24rem;
    max-width: calc(100vw - 2rem);
    max-height: calc(100dvh - var(--bar-h) - 1rem);
    overflow-y: auto;
    padding: 0.75rem;
    background: var(--surface0);
    border-radius: var(--r-sm);
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
  }
  .panel :global(.placeholder) {
    background: var(--base);
  }
  .group {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .eyebrow,
  .none {
    margin: 0;
    padding: 0 0.45rem;
  }
  .none {
    color: var(--text-muted);
    font-size: 0.82rem;
  }
  a {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.45rem;
    border-radius: var(--r-xs);
    color: var(--text);
    text-decoration: none;
    font-size: 0.82rem;
  }
  a[aria-selected='true'] {
    background: var(--surface1);
  }
  .text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    line-height: 1.3;
  }
  .label,
  .sub {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub {
    color: var(--text-muted);
    font-size: 0.74rem;
  }
  .count {
    font-family: var(--font-mono);
    font-size: 0.74rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 640px) {
    input {
      width: 8rem;
    }
  }
</style>
