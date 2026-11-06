<script lang="ts">
  let { src, alt, size }: { src: string | null | undefined; alt: string; size: number } = $props();

  let failedSrc = $state<string | null>(null);
</script>

{#if src && failedSrc !== src}
  <img {src} {alt} width={size} height={size} loading="lazy" onerror={() => (failedSrc = src ?? null)} />
{:else}
  <span class="placeholder" aria-hidden="true" data-testid="cover-placeholder" style="width: {size}px; height: {size}px"></span>
{/if}

<style>
  img,
  .placeholder {
    display: block;
    flex: none;
    border-radius: var(--r-xs);
    background: var(--surface0);
  }
  img {
    object-fit: cover;
  }
</style>
