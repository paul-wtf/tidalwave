<script lang="ts">
  import {
    statsApi, ApiError,
    type Summary, type MetricPoint, type RecentItem,
    type ArtistCount, type TrackCount, type AlbumCount
  } from '$lib/api/client';
  import { loadMe } from '$lib/stores/auth';
  import { rangeQuery } from '$lib/stores/range';
  import { formatCount, formatDuration } from '$lib/format';
  import StatCard from './StatCard.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';
  import ListeningClock from './ListeningClock.svelte';
  import WeekdayChart from './WeekdayChart.svelte';
  import RecentList from './RecentList.svelte';

  // `token` switches to shared-link mode: data comes from the shared endpoints
  // (range fixed by the share) instead of the global range store.
  let { token, errorMessage = 'Could not load your stats. Please try again.' }:
    { token?: string; errorMessage?: string } = $props();

  const EMPTY: Summary = {
    total_listens: 0, distinct_artists: 0, distinct_tracks: 0, distinct_albums: 0, total_seconds: 0
  };

  type ListItem = { label: string; count: number; query?: string };
  let summary = $state<Summary>(EMPTY);
  let metrics = $state<MetricPoint[]>([]);
  let artists = $state<ListItem[]>([]);
  let tracks = $state<ListItem[]>([]);
  let albums = $state<ListItem[]>([]);
  let hours = $state<number[]>(new Array(24).fill(0));
  let days = $state<number[]>(new Array(7).fill(0));
  let recent = $state<RecentItem[]>([]);
  let error = $state(false);

  const base = $derived(token ? `/s/${token}` : '');

  function apply(
    s: Summary, m: MetricPoint[], ar: ArtistCount[], tr: TrackCount[], al: AlbumCount[],
    cl: number[], wd: number[], rc: RecentItem[]
  ) {
    summary = s;
    metrics = m;
    artists = ar.map((x) => ({ label: x.artist, count: x.count, query: x.artist }));
    tracks = tr.map((x) => ({ label: `${x.track} — ${x.artist}`, count: x.count, query: `${x.artist} ${x.track}` }));
    albums = al.map((x) => ({
      label: x.album ?? 'Unknown album', count: x.count, query: x.album ?? undefined
    }));
    hours = cl; days = wd; recent = rc;
  }

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    (async () => {
      try {
        const [s, m, ar, tr, al, cl, wd, rc] = await Promise.all([
          client.summary(params, q?.compare), client.metricsOverTime(bucket, params),
          client.topArtists(5, params), client.topTracks(5, params), client.topAlbums(5, params),
          client.clock(params), client.weekday(params), client.recent(12, params)
        ]);
        apply(s, m, ar, tr, al, cl, wd, rc);
        error = false;
      } catch (e) {
        if (!shared && e instanceof ApiError && e.status === 401) await loadMe();
        else error = true;
      }
    })();
  });

  const listensTrend = $derived(metrics.map((m) => ({ period: m.period, value: m.listens })));
  const timeTrend = $derived(metrics.map((m) => ({ period: m.period, value: m.seconds })));
  const artistsTrend = $derived(metrics.map((m) => ({ period: m.period, value: m.artists })));
  function change(cur: number, prev: number | undefined): number | null {
    return token != null || !prev ? null : (cur - prev) / prev;
  }
  const prev = $derived(summary.previous);
  const timePending = $derived(summary.total_listens > 0 && summary.total_seconds === 0);
</script>

{#if error}
  <p class="error">{errorMessage}</p>
{:else}
  <div class="dashboard">
    <div class="row stats">
      <StatCard label="Songs listened" value={formatCount(summary.total_listens)}
        delta={change(summary.total_listens, prev?.total_listens)} />
      <StatCard
        label="Time listened"
        value={formatDuration(summary.total_seconds)}
        delta={change(summary.total_seconds, prev?.total_seconds)}
        sub={timePending ? 'resolving durations…' : undefined}
      />
      <StatCard label="Artists" value={formatCount(summary.distinct_artists)}
        delta={change(summary.distinct_artists, prev?.distinct_artists)} />
      <StatCard label="Albums" value={formatCount(summary.distinct_albums)}
        delta={change(summary.distinct_albums, prev?.distinct_albums)} />
    </div>
    <div class="row trends">
      <AreaTrend title="Listens over time" points={listensTrend} />
      <AreaTrend title="Time listened" points={timeTrend} formatValue={formatDuration} />
      <AreaTrend title="Artists over time" points={artistsTrend} />
    </div>
    <div class="row charts">
      <ListeningClock {hours} />
      <WeekdayChart {days} />
    </div>
    <div class="row tops">
      <TopList title="Top Artists" items={artists} href="{base}/artists" />
      <TopList title="Top Tracks" items={tracks} href="{base}/tracks" />
      <TopList title="Top Albums" items={albums} href="{base}/albums" />
    </div>
    <RecentList items={recent} />
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
