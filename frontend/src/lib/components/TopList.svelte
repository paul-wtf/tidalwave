<script lang="ts">
  import PlatformLinks from './PlatformLinks.svelte';

  type Item = { label: string; count: number; query?: string };
  let { title, items, initial = 5, href }:
    { title: string; items: Item[]; initial?: number; href?: string } =
    $props();
  const max = $derived(items.reduce((m, i) => Math.max(m, i.count), 0) || 1);

  let expanded = $state(false);
  const visible = $derived(expanded ? items : items.slice(0, initial));
</script>

<section class="glass">
  <div class="head">
    <h2>{title}</h2>
    {#if href}<a class="all" {href}>View all →</a>{/if}
  </div>
  {#if items.length === 0}
    <p class="empty">No data yet.</p>
  {:else}
    <ol>
      {#each visible as item, i}
        <li>
          <span class="bar" class:top={i === 0} style="width: {(item.count / max) * 100}%"></span>
          <span class="rank">{i + 1}</span>
          <span class="label">{item.label}</span>
          {#if item.query}
            <span class="links"><PlatformLinks query={item.query} /></span>
          {/if}
          <span class="count">{item.count}</span>
        </li>
      {/each}
    </ol>
    {#if !href && items.length > initial}
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
  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin: 0 0 1rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
    margin: 0;
  }
  .all {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-muted);
    text-decoration: none;
    white-space: nowrap;
    transition: color var(--dur-fast) var(--ease-out);
  }
  .all:hover {
    color: var(--accent-text);
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  li {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.45rem 0.6rem;
    border-radius: var(--r-sm);
    overflow: hidden;
  }
  .bar {
    position: absolute;
    inset: 0;
    background: var(--accent);
    opacity: 0.12;
    z-index: 0;
    border-radius: var(--r-sm);
    transition: width var(--dur) var(--ease-out);
  }
  .bar.top {
    opacity: 0.22;
  }
  .rank {
    z-index: 1;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-dim);
    min-width: 1.2rem;
  }
  .label {
    z-index: 1;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .links {
    z-index: 1;
    display: inline-flex;
    opacity: 0;
    transition: opacity var(--dur-fast) var(--ease-out);
  }
  li:hover .links,
  li:focus-within .links {
    opacity: 1;
  }
  /* Touch devices have no hover — always show the platform links there. */
  @media (hover: none) {
    .links { opacity: 1; }
  }
  .count {
    z-index: 1;
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
  .more {
    margin-top: 0.6rem;
    width: 100%;
    background: none;
    border: 0;
    padding: 0.6rem 0 0.1rem;
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
