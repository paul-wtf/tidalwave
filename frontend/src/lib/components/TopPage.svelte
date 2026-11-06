<script lang="ts">
  import { statsApi, ApiError, type MetricPoint } from '$lib/api/client';
  import { loadMe } from '$lib/stores/auth';
  import { rangeQuery } from '$lib/stores/range';
  import TopList from './TopList.svelte';
  import AreaTrend from './AreaTrend.svelte';

  // `token` switches to shared-link mode (data from the shared endpoints).
  let { kind, token, errorMessage = 'Could not load your stats. Please try again.' }:
    { kind: 'artists' | 'tracks' | 'albums'; token?: string; errorMessage?: string } = $props();

  const TITLES = { artists: 'Top Artists', tracks: 'Top Tracks', albums: 'Top Albums' };
  const TRENDS = { artists: 'Artists over time', tracks: 'Listens over time', albums: 'Albums over time' };

  let items = $state<{ label: string; count: number; query?: string }[]>([]);
  let metrics = $state<MetricPoint[]>([]);
  let error = $state(false);

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
          items = (await client.topArtists(100, params)).map((r) => ({ label: r.artist, count: r.count, query: r.artist }));
        } else if (k === 'tracks') {
          items = (await client.topTracks(100, params)).map((r) => ({ label: `${r.track} — ${r.artist}`, count: r.count, query: `${r.artist} ${r.track}` }));
        } else {
          items = (await client.topAlbums(100, params)).map((r) => ({ label: r.album ?? 'Unknown album', count: r.count, query: r.album ?? undefined }));
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
    <TopList title={TITLES[kind]} items={items} initial={1000} />
  </div>
{/if}

<style>
  .error {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
