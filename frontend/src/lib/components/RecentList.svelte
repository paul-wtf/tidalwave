<script lang="ts">
  import { formatDateTime } from '$lib/format';
  import type { RecentItem } from '$lib/api/client';
  import { artistHref, trackHref } from '$lib/links';
  import Cover from './Cover.svelte';
  let { items, initial = 6, base = '', tz = 'UTC' }:
    { items: RecentItem[]; initial?: number; base?: string; tz?: string | null } = $props();

  let expanded = $state(false);
  const visible = $derived(expanded ? items : items.slice(0, initial));
</script>

<section class="glass">
  <h2>Recent</h2>
  {#if items.length === 0}
    <p class="empty">No data yet.</p>
  {:else}
    <ul>
      {#each visible as item (item.played_at + item.track)}
        <li>
          <span class="cover"><Cover src={item.image_url} alt="" size={40} /></span>
          <a class="track" href={trackHref(base, item.artist, item.track)}>{item.track}</a>
          <a class="artist" href={artistHref(base, item.artist)}>{item.artist}</a>
          <time>{formatDateTime(item.played_at, tz)}</time>
        </li>
      {/each}
    </ul>
    {#if items.length > initial}
      <button class="more" onclick={() => (expanded = !expanded)}>
        {expanded ? 'Show less' : `Show ${items.length - initial} more`}
      </button>
    {/if}
  {/if}
</section>

<style>
  section {
    padding: 1.4rem 1.5rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
    margin: 0 0 1rem;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li {
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-areas: 'cover track time' 'cover artist time';
    column-gap: 0.75rem;
    align-items: baseline;
    padding: 0.55rem 0.6rem;
    border-radius: var(--r-xs);
  }
  /* Separation via zebra shading (mantle on odd rows) instead of border
     lines. */
  li:nth-child(odd) {
    background: var(--mantle);
  }
  .cover {
    grid-area: cover;
    display: flex;
    margin-right: 0.25rem;
  }
  a {
    color: inherit;
    text-decoration: none;
  }
  a:hover {
    color: var(--accent-text);
  }
  .track {
    grid-area: track;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .artist {
    grid-area: artist;
    justify-self: start;
    max-width: 100%;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  time {
    grid-area: time;
    align-self: center;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
  .more {
    margin-top: 0.4rem;
    width: 100%;
    background: none;
    border: 0;
    padding: 0.65rem 0.6rem 0.1rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.72rem;
    text-transform: lowercase;
    text-align: left;
    cursor: pointer;
    transition: color var(--dur-fast) var(--ease-out);
  }
  .more:hover {
    color: var(--accent-text);
  }
</style>
