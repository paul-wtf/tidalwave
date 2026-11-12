<script lang="ts">
  import { onMount } from 'svelte';
  import type { AlbumCount } from '$lib/api/client';
  import {
    COLLAGE_SIZES, TILE, collageAlbums, collageColors, drawCollage, loadCover,
    type CollageSize
  } from '$lib/collage';

  let { albums, onclose }: { albums: AlbumCount[]; onclose: () => void } = $props();

  let size = $state<CollageSize>(3);
  let ready = $state(false);
  let dialog: HTMLDialogElement | undefined = $state();
  let canvas: HTMLCanvasElement | undefined = $state();

  const covers = new Map<string | null, Promise<HTMLImageElement | null>>();
  let latest = 0;

  const picked = $derived(collageAlbums(albums, size));

  onMount(() => dialog?.showModal());

  function cover(url: string | null) {
    let pending = covers.get(url);
    if (!pending) {
      pending = loadCover(url);
      covers.set(url, pending);
    }
    return pending;
  }

  $effect(() => {
    const n = size;
    const list = picked;
    const target = canvas;
    if (!target) return;
    const ticket = ++latest;
    ready = false;
    void (async () => {
      const [images] = await Promise.all([
        Promise.all(list.map((a) => cover(a.url))),
        document.fonts?.load('700 26px "JetBrains Mono Variable"').catch(() => undefined)
      ]);
      if (ticket !== latest) return;
      target.width = n * TILE;
      target.height = n * TILE;
      const ctx = target.getContext('2d');
      if (!ctx) return;
      drawCollage(
        ctx, n,
        list.map((a, i) => ({ album: a.album, artist: a.artist, image: images[i] })),
        collageColors(document.documentElement)
      );
      ready = true;
    })();
  });

  function download() {
    canvas?.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `tidalwave-collage-${size}x${size}.png`;
      link.click();
      URL.revokeObjectURL(url);
    }, 'image/png');
  }

  function onDialogClick(e: MouseEvent) {
    if (e.target === dialog) dialog?.close();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog bind:this={dialog} aria-labelledby="collage-title" {onclose} onclick={onDialogClick}>
  <div class="body">
    <div class="head">
      <h2 id="collage-title">Cover collage</h2>
      <button type="button" class="close" aria-label="Close" onclick={() => dialog?.close()}>×</button>
    </div>
    <fieldset>
      <legend>Grid</legend>
      {#each COLLAGE_SIZES as n (n)}
        <label>
          <input type="radio" name="collage-size" value={n} bind:group={size} />
          <span>{n}×{n}</span>
        </label>
      {/each}
    </fieldset>
    <canvas bind:this={canvas} data-testid="collage-canvas" aria-label="Collage preview"></canvas>
    {#if picked.length < size * size}
      <p class="note">Only {picked.length} {picked.length === 1 ? 'album' : 'albums'} in this range.</p>
    {/if}
    <button type="button" class="download" disabled={!ready} onclick={download}>Download PNG</button>
  </div>
</dialog>

<style>
  dialog {
    padding: 0;
    border: 0;
    border-radius: var(--r-lg);
    background: var(--base);
    color: var(--text);
    box-shadow: var(--glass-shadow);
    width: min(26rem, calc(100vw - 2rem));
    max-height: calc(100dvh - 2rem);
  }
  dialog::backdrop {
    background: color-mix(in srgb, var(--crust) 75%, transparent);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    padding: 1.2rem 1.3rem 1.3rem;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }
  h2 {
    font-size: 1.2rem;
  }
  fieldset {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    border: 0;
  }
  legend {
    float: left;
    margin-right: 0.6rem;
    padding: 0;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  label {
    cursor: pointer;
  }
  label input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }
  label span {
    display: block;
    padding: 0.35rem 0.8rem;
    border-radius: var(--r-sm);
    background: var(--surface0);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
  }
  label input:checked + span {
    background: var(--accent-text);
    color: var(--accent-contrast);
  }
  label input:focus-visible + span {
    box-shadow: 0 0 0 2px var(--base), 0 0 0 4px var(--accent-text);
  }
  canvas {
    display: block;
    width: 100%;
    aspect-ratio: 1;
    border-radius: var(--r-sm);
    background: var(--surface0);
  }
  .note {
    margin: 0;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  button {
    border: 0;
    border-radius: var(--r-sm);
    font-size: 0.85rem;
    cursor: pointer;
  }
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--base), 0 0 0 4px var(--accent-text);
  }
  .close {
    width: 2rem;
    height: 2rem;
    background: var(--surface0);
    color: var(--text);
    font-size: 1.1rem;
    line-height: 1;
  }
  .download {
    padding: 0.55rem 1rem;
    background: var(--accent-text);
    color: var(--accent-contrast);
    font-weight: 600;
  }
  .download:disabled {
    opacity: 0.55;
    cursor: default;
  }
</style>
