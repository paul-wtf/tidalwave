<script lang="ts">
  import type { Snippet } from 'svelte';
  import { coverAccent, extractCoverColor, type CoverColor } from '$lib/coverColor';
  import { theme } from '$lib/stores/theme';
  import Cover from './Cover.svelte';
  import PlatformLinks from './PlatformLinks.svelte';
  import StatCard from './StatCard.svelte';

  let { title, query, image, stats, links, children }: {
    title: string;
    query: string;
    image: string | null | undefined;
    stats: {
      label: string; value: string | number; format?: (n: number) => string;
      sub?: string; compact?: boolean;
    }[];
    links?: Snippet;
    children?: Snippet;
  } = $props();

  let color = $state<CoverColor | null>(null);

  $effect(() => {
    if (!image) {
      color = null;
      return;
    }
    let stale = false;
    extractCoverColor(image).then((found) => {
      if (!stale) color = found;
    });
    return () => {
      stale = true;
    };
  });

  const style = $derived.by(() => {
    if (!color) return undefined;
    const { accent, text, soft } = coverAccent(color, $theme);
    return `--accent: ${accent}; --accent-text: ${text}; --accent-soft: ${soft}; --title: ${text}`;
  });
</script>

<div class="tinted" {style}>
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
        <StatCard label={s.label} value={s.value} format={s.format} sub={s.sub} compact={s.compact} />
      {/each}
    </div>
  </header>
  {@render children?.()}
</div>

<style>
  /* Only carries the accent tokens: header and chart stay direct children
     of the page's layout. */
  .tinted {
    display: contents;
  }
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
    color: var(--title, var(--text));
    transition: color var(--dur-fast) var(--ease-out);
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
  .head .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 1rem;
  }
</style>
