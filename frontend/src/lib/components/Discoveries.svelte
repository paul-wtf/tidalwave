<script lang="ts">
  import type { Discoveries } from '$lib/api/client';
  import { formatCount, formatLocalDate } from '$lib/format';
  import { artistHref, trackHref } from '$lib/links';
  import Cover from './Cover.svelte';

  let { discoveries, base = '', tz = 'UTC' }:
    { discoveries: Discoveries; base?: string; tz?: string | null } = $props();

  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;
</script>

<section class="glass">
  <h2>Discoveries</h2>

  <h3>New artists</h3>
  {#if discoveries.new_artists.length === 0}
    <p class="empty">No new artists in this range.</p>
  {:else}
    <ul>
      {#each discoveries.new_artists as a (a.artist)}
        <li>
          <Cover src={a.image_url} alt="" size={40} />
          <a class="name" href={artistHref(base, a.artist)}>{a.artist}</a>
          <span class="meta">{listens(a.listens)}, first heard {formatLocalDate(a.first_listen, tz)}</span>
        </li>
      {/each}
    </ul>
  {/if}

  <h3>New tracks ({formatCount(discoveries.new_tracks_count)})</h3>
  {#if discoveries.new_tracks.length === 0}
    <p class="empty">No new tracks in this range.</p>
  {:else}
    <ul>
      {#each discoveries.new_tracks as t (`${t.artist}\u0000${t.track}`)}
        <li>
          <a class="name" href={trackHref(base, t.artist, t.track)}>{t.track}</a>
          <a class="artist" href={artistHref(base, t.artist)}>{t.artist}</a>
          <span class="meta">{listens(t.listens)}, first heard {formatLocalDate(t.first_listen, tz)}</span>
        </li>
      {/each}
    </ul>
  {/if}

  <h3>Rediscoveries</h3>
  {#if discoveries.rediscoveries.length === 0}
    <p class="empty">No rediscoveries in this range.</p>
  {:else}
    <ul>
      {#each discoveries.rediscoveries as r (r.artist)}
        <li>
          <a class="name" href={artistHref(base, r.artist)}>{r.artist}</a>
          <span class="meta">
            back after {formatCount(r.gap_days)} days, last heard {formatLocalDate(r.previous_listen, tz)},
            {listens(r.listens)}
          </span>
        </li>
      {/each}
    </ul>
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
  h3 {
    font-size: 1rem;
    color: var(--text-muted);
    margin: 1.2rem 0 0.5rem;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    padding: 0.4rem 0.6rem;
    border-radius: var(--r-xs);
  }
  li:nth-child(odd) {
    background: var(--mantle);
  }
  a {
    color: inherit;
    text-decoration: none;
  }
  a:hover {
    color: var(--accent-text);
  }
  .artist,
  .meta {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .meta {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
