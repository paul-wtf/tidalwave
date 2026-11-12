<script lang="ts">
  import type { Genres } from '$lib/api/client';
  import { formatCount } from '$lib/format';
  import { genreHref } from '$lib/links';

  let { genres, base = '' }: { genres: Genres; base?: string } = $props();

  const top = $derived(genres.genres.slice(0, 10));
  const max = $derived(Math.max(1, ...top.map((g) => g.listens)));
  const pending = $derived(genres.tagged_artists < genres.artists);
</script>

<section class="glass">
  <h2>Genres</h2>
  {#if genres.artists === 0}
    <p class="empty">No data yet.</p>
  {:else if genres.tagged_artists === 0}
    <p class="note" role="status">Genres are still being fetched from Last.fm, a few artists with every sync.</p>
  {:else}
    {#if pending}
      <p class="note" role="status">
        Tags for {formatCount(genres.tagged_artists)} of {formatCount(genres.artists)} artists so far.
        The ranking changes as the rest arrive.
      </p>
    {/if}
    {#if top.length === 0}
      {#if !pending}<p class="empty">Last.fm has no genre tags for these artists.</p>{/if}
    {:else}
      <ol>
        {#each top as g (g.genre)}
          <li title="{formatCount(g.artists)} {g.artists === 1 ? 'artist' : 'artists'}">
            <a class="name" href={genreHref(base, g.genre)}>{g.genre}</a>
            <span class="track" aria-hidden="true">
              <span class="fill" style="width: {(g.listens / max) * 100}%"></span>
            </span>
            <span class="count">{formatCount(g.listens)}</span>
          </li>
        {/each}
      </ol>
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
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: minmax(5rem, max-content) minmax(0, 1fr) max-content;
    column-gap: 0.9rem;
    row-gap: 0.55rem;
    align-items: center;
  }
  li {
    display: grid;
    grid-column: 1 / -1;
    grid-template-columns: subgrid;
    align-items: center;
  }
  .name {
    color: var(--text);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 14rem;
    transition: color var(--dur-fast) var(--ease-out);
  }
  .name:hover {
    color: var(--accent-text);
  }
  .track {
    display: block;
    height: 0.8rem;
  }
  .fill {
    display: block;
    height: 100%;
    min-width: 2px;
    border-radius: 0 var(--r-xs) var(--r-xs) 0;
    background: var(--accent);
    transition: width var(--dur) var(--ease-out);
  }
  .count {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  .note {
    margin: 0 0 1rem;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
