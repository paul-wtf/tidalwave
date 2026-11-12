<script lang="ts">
  import type { AlbumRuns } from '$lib/api/client';
  import { formatCount, formatDuration, formatLocalDate, formatLongDateTime } from '$lib/format';
  import { albumHref, artistHref } from '$lib/links';
  import Cover from './Cover.svelte';

  // `single`: the runs of one album, for its own page. The heading carries the
  // count and the rows drop the names.
  let { runs, base = '', tz = 'UTC', single = false }:
    { runs: AlbumRuns; base?: string; tz?: string | null; single?: boolean } = $props();

  const heading = $derived(
    !single ? 'Albums played through'
      : runs.total === 1 ? 'Played through once'
        : `Played through ${formatCount(runs.total)} times`
  );
  const more = $derived(runs.total - runs.runs.length);

  function size(run: AlbumRuns['runs'][number]): string {
    const tracks = `${formatCount(run.tracks)} tracks`;
    return run.seconds > 0 ? `${tracks}, ${formatDuration(run.seconds)}` : tracks;
  }
</script>

<section class="glass">
  <h2>{heading}</h2>
  {#if runs.runs.length === 0}
    <p class="empty">No album played through in this range.</p>
  {:else}
    <ul>
      {#each runs.runs as run (`${run.started_at}\u0000${run.artist}\u0000${run.album}`)}
        <li class:single>
          {#if single}
            <span class="name">{formatLongDateTime(run.started_at, tz)}</span>
            <span class="meta">{size(run)}</span>
          {:else}
            <Cover src={run.image_url} alt="" size={40} />
            <span class="who">
              <a class="name" href={albumHref(base, run.artist, run.album)}>{run.album}</a>
              <a class="artist" href={artistHref(base, run.artist)}>{run.artist}</a>
            </span>
            <span class="meta">{size(run)}, {formatLocalDate(run.started_at, tz)}</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#if more > 0}
      <p class="more">and {formatCount(more)} more in this range</p>
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
    display: flex;
    gap: 0.75rem;
    align-items: center;
    padding: 0.4rem 0.6rem;
    border-radius: var(--r-xs);
    min-width: 0;
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
  .who {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    min-width: 0;
  }
  .name,
  .artist {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .artist {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .meta {
    margin-left: auto;
    flex: none;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  @media (max-width: 640px) {
    li:not(.single) {
      flex-wrap: wrap;
      row-gap: 0.15rem;
    }
    .who {
      flex: 1 1 0;
    }
    li:not(.single) .meta {
      flex: 1 1 100%;
      min-width: 0;
      margin-left: 0;
      padding-left: calc(40px + 0.75rem);
      overflow-wrap: anywhere;
    }
  }
  .more {
    margin: 0.7rem 0 0;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
