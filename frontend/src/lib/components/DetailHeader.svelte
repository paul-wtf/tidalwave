<script lang="ts">
  import type { Snippet } from 'svelte';
  import Cover from './Cover.svelte';
  import PlatformLinks from './PlatformLinks.svelte';
  import StatCard from './StatCard.svelte';

  let { title, query, image, stats, links }: {
    title: string;
    query: string;
    image: string | null | undefined;
    stats: { label: string; value: string }[];
    links?: Snippet;
  } = $props();
</script>

<header class="head">
  <div class="id">
    <Cover src={image} alt="" size={96} />
    <div class="text">
      <h1>{title}</h1>
      {#if links}<p class="links">{@render links()}</p>{/if}
      <PlatformLinks {query} />
    </div>
  </div>
  <div class="stats">
    {#each stats as s (s.label)}
      <StatCard label={s.label} value={s.value} />
    {/each}
  </div>
</header>

<style>
  .head {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }
  .id {
    display: flex;
    align-items: center;
    gap: 1.25rem;
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    min-width: 0;
  }
  h1 {
    margin: 0;
    font-size: 2rem;
    overflow-wrap: anywhere;
  }
  .links {
    margin: 0;
    color: var(--text-muted);
  }
  .links :global(a) {
    color: inherit;
    text-decoration: none;
  }
  .links :global(a:hover) {
    color: var(--accent-text);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 1rem;
  }
</style>
