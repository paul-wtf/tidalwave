<script lang="ts">
  let { src, alt, size }: { src: string | null | undefined; alt: string; size: number } = $props();

  let failed = $state(false);
  $effect(() => {
    src;
    failed = false;
  });
</script>

{#if src && !failed}
  <img {src} {alt} width={size} height={size} loading="lazy" onerror={() => (failed = true)} />
{:else}
  <span class="placeholder" data-testid="cover-placeholder" style="width: {size}px; height: {size}px"></span>
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
