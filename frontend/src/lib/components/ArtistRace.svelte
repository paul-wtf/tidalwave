<script lang="ts">
  import { onDestroy } from 'svelte';
  import { statsApi, type ArtistRace } from '$lib/api/client';
  import { loadDetail } from '$lib/detailLoader';
  import { formatCount, formatPeriod } from '$lib/format';
  import { artistHref } from '$lib/links';
  import { prefersReducedMotion } from '$lib/motion';
  import { RACE_SIZE, standings, stepMs } from '$lib/race';
  import { rangeQuery } from '$lib/stores/range';
  import Cover from './Cover.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const still = prefersReducedMotion();

  let race = $state<ArtistRace | null>(null);
  let error = $state(false);
  let frame = $state(0);
  let playing = $state(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  const last = $derived(race ? race.periods.length - 1 : 0);
  const table = $derived(race ? standings(race.artists, frame, RACE_SIZE) : null);
  const places = $derived(Math.min(RACE_SIZE, race?.artists.length ?? 0));
  const date = $derived(race && race.periods.length ? formatPeriod(race.periods[frame], race.bucket) : '');

  function pause() {
    clearInterval(timer);
    playing = false;
  }

  function play() {
    if (!race) return;
    if (frame >= last) frame = 0;
    playing = true;
    timer = setInterval(() => {
      if (frame >= last) return pause();
      frame += 1;
      if (frame >= last) pause();
    }, stepMs(race.periods.length));
  }

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    pause();
    return loadDetail(
      shared,
      () => client.artistRace(q?.bucket, q?.params),
      (r) => {
        race = r;
        frame = Math.max(0, r.periods.length - 1);
      },
      (st) => (error = st !== 'ok')
    );
  });

  onDestroy(pause);
</script>

<section class="glass">
  <div class="head">
    <h2>Race</h2>
    {#if date}<span class="date">{date}</span>{/if}
  </div>
  {#if error}
    <p class="empty">Could not load the race. Please try again.</p>
  {:else if race && table}
    {#if race.periods.length === 0}
      <p class="empty">No data yet.</p>
    {:else}
      <ol style="--places: {places}">
        {#each race.artists as a, i (a.artist)}
          {@const s = table.rows[i]}
          <li
            class:out={!s.shown}
            data-rank={s.rank}
            style="--place: {Math.min(s.rank, places)}"
            aria-hidden={!s.shown}
          >
            <span class="who">
              <Cover src={a.image_url} alt="" size={24} />
              <a class="name" href={artistHref(base, a.artist)} tabindex={s.shown ? 0 : -1}>{a.artist}</a>
            </span>
            <span class="track"><span class="fill" style="width: {(s.total / table.max) * 100}%"></span></span>
            <span class="count">{formatCount(s.total)}</span>
          </li>
        {/each}
      </ol>
      <div class="controls">
        {#if !still}
          <button type="button" onclick={() => (playing ? pause() : play())}>
            {playing ? 'Pause' : 'Play'}
          </button>
        {/if}
        <input
          type="range"
          min="0"
          max={last}
          step="1"
          value={frame}
          aria-label="Position in the race"
          aria-valuetext={date}
          oninput={(e) => {
            pause();
            frame = Number(e.currentTarget.value);
          }}
        />
      </div>
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
  .date {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.35rem;
    color: var(--accent-text);
    font-variant-numeric: tabular-nums;
  }
  ol {
    --row: 2.5rem;
    list-style: none;
    margin: 0;
    padding: 0;
    position: relative;
    height: calc(var(--places) * var(--row));
    overflow: hidden;
  }
  li {
    position: absolute;
    inset: 0 0 auto 0;
    height: var(--row);
    display: grid;
    grid-template-columns: minmax(0, 12rem) minmax(0, 1fr) 3.5rem;
    align-items: center;
    column-gap: 0.9rem;
    transform: translateY(calc(var(--place) * var(--row)));
    transition:
      transform var(--dur) var(--ease-out),
      opacity var(--dur-fast) var(--ease-out);
  }
  li.out {
    opacity: 0;
    pointer-events: none;
  }
  .who {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-width: 0;
  }
  .name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
    text-decoration: none;
  }
  .name:hover {
    color: var(--accent-text);
  }
  .track {
    display: block;
    height: 1.4rem;
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
  .controls {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin-top: 1rem;
  }
  button {
    flex: none;
    min-width: 4.5rem;
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    background: var(--surface0);
    color: var(--text);
    font-family: var(--font-body);
    font-size: 0.82rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  button:hover {
    background: var(--surface1);
  }
  input[type='range'] {
    flex: 1;
    min-width: 0;
    accent-color: var(--accent-text);
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
  @media (max-width: 640px) {
    li {
      grid-template-columns: minmax(0, 7.5rem) minmax(0, 1fr) 3rem;
      column-gap: 0.6rem;
    }
  }
</style>
