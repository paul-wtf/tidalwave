<script lang="ts">
  import { LINKHOP_BRAND, PLATFORMS, linkhopSearch } from '$lib/platforms';
  import { config } from '$lib/stores/config';
  import PlatformIcon from './PlatformIcon.svelte';

  // `query` is the search text (e.g. "Daft Punk Around the World"). Each icon
  // opens that search on the matching platform in a new tab.
  let { query }: { query: string } = $props();
</script>

<span class="platforms">
  {#each PLATFORMS as p (p.id)}
    <a
      class="platform"
      style="--brand: {p.brand}"
      href={p.search(query)}
      target="_blank"
      rel="noopener noreferrer"
      title="Open on {p.name}"
      aria-label="Open “{query}” on {p.name}"
      onclick={(e) => e.stopPropagation()}
    >
      <PlatformIcon id={p.id} />
    </a>
  {/each}
  {#if $config.linkhopUrl}
    <a
      class="platform"
      style="--brand: {LINKHOP_BRAND}"
      href={linkhopSearch($config.linkhopUrl, query)}
      target="_blank"
      rel="noopener noreferrer"
      title="Find on every service with linkhop"
      aria-label="Find “{query}” on every service with linkhop"
      onclick={(e) => e.stopPropagation()}
    >
      <PlatformIcon id="linkhop" />
    </a>
  {/if}
</span>

<style>
  .platforms {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
  }
  .platform {
    width: 1rem;
    height: 1rem;
    color: var(--text-dim);
    transition: color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
  }
  .platform:hover,
  .platform:focus-visible {
    color: var(--brand);
    transform: translateY(-1px);
    outline: none;
  }
</style>
