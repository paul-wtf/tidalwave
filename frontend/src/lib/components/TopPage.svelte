<script lang="ts">
  import { statsApi, ApiError, type AlbumCount, type MetricPoint } from '$lib/api/client';
  import { loadMe } from '$lib/stores/auth';
  import { rangeQuery } from '$lib/stores/range';
  import { artistItems, trackItems, albumItems, type ListItem } from '$lib/listItems';
  import TopList from './TopList.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import CollageDialog from './CollageDialog.svelte';

  // `token` switches to shared-link mode (data from the shared endpoints).
  let { kind, token, errorMessage = 'Could not load your stats. Please try again.' }:
    { kind: 'artists' | 'tracks' | 'albums'; token?: string; errorMessage?: string } = $props();

  const TITLES = { artists: 'Top Artists', tracks: 'Top Tracks', albums: 'Top Albums' };
  const TRENDS = { artists: 'Artists over time', tracks: 'Listens over time', albums: 'Albums over time' };

  let items = $state<ListItem[]>([]);
  const base = $derived(token ? `/s/${token}` : '');
  let metrics = $state<MetricPoint[]>([]);
  let error = $state(false);
  let albums = $state<AlbumCount[]>([]);
  let collageOpen = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    const k = kind;
    (async () => {
      try {
        const metricsPromise = client.metricsOverTime(bucket, params);
        if (k === 'artists') {
          items = artistItems(await client.topArtists(100, params), base);
        } else if (k === 'tracks') {
          items = trackItems(await client.topTracks(100, params), base);
        } else {
          albums = await client.topAlbums(100, params);
          items = albumItems(albums, base);
        }
        metrics = await metricsPromise;
        error = false;
      } catch (e) {
        if (!shared && e instanceof ApiError && e.status === 401) await loadMe();
        else error = true;
      }
    })();
  });

  const trend = $derived(
    metrics.map((m) => ({
      period: m.period,
      value: kind === 'artists' ? m.artists : kind === 'albums' ? m.albums : m.listens
    }))
  );
</script>

{#if error}
  <p class="error">{errorMessage}</p>
{:else}
  <div class="dashboard">
    <AreaTrend title={TRENDS[kind]} points={trend} />
    <TopList title={TITLES[kind]} items={items} initial={1000} covers={kind !== 'tracks'}>
      {#snippet actions()}
        {#if kind === 'albums'}
          <button
            type="button"
            class="collage"
            disabled={!albums.some((a) => a.album != null)}
            onclick={() => (collageOpen = true)}
          >Collage</button>
        {/if}
      {/snippet}
    </TopList>
  </div>
  {#if collageOpen}
    <CollageDialog {albums} onclose={() => (collageOpen = false)} />
  {/if}
{/if}

<style>
  .collage {
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    background: var(--surface0);
    color: var(--text);
    font-size: 0.82rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .collage:hover:not(:disabled) {
    background: var(--surface1);
  }
  .collage:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .error {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
