<script lang="ts">
  import {
    statsApi, ApiError,
    type Summary, type MetricPoint, type RecentItem,
    type ArtistCount, type TrackCount, type AlbumCount
  } from '$lib/api/client';
  import { auth, loadMe } from '$lib/stores/auth';
  import { rangeQuery } from '$lib/stores/range';
  import { formatDuration } from '$lib/format';
  import { artistItems, trackItems, albumItems, type ListItem } from '$lib/listItems';
  import StatCard from './StatCard.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';
  import ListeningClock from './ListeningClock.svelte';
  import WeekdayChart from './WeekdayChart.svelte';
  import RecentList from './RecentList.svelte';
  import TrendWave from './TrendWave.svelte';

  // `token` switches to shared-link mode: data comes from the shared endpoints
  // (range fixed by the share) instead of the global range store.
  let { token, errorMessage = 'Could not load your stats. Please try again.' }:
    { token?: string; errorMessage?: string } = $props();

  const EMPTY: Summary = {
    total_listens: 0, distinct_artists: 0, distinct_tracks: 0, distinct_albums: 0, total_seconds: 0
  };

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
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));

  function apply(
    s: Summary, m: MetricPoint[], ar: ArtistCount[], tr: TrackCount[], al: AlbumCount[],
    cl: number[], wd: number[], rc: RecentItem[]
  ) {
    summary = s;
    metrics = m;
    artists = artistItems(ar, base);
    tracks = trackItems(tr, base);
    albums = albumItems(al, base);
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
  <TrendWave values={metrics.map((m) => m.listens)} />
  <div class="dashboard">
    <div class="row stats">
      <StatCard label="Songs listened" value={summary.total_listens}
        delta={change(summary.total_listens, prev?.total_listens)} />
      <StatCard
        label="Time listened"
        value={summary.total_seconds}
        format={formatDuration}
        delta={change(summary.total_seconds, prev?.total_seconds)}
        sub={timePending ? 'resolving durations…' : undefined}
      />
      <StatCard label="Artists" value={summary.distinct_artists}
        delta={change(summary.distinct_artists, prev?.distinct_artists)} />
      <StatCard label="Albums" value={summary.distinct_albums}
        delta={change(summary.distinct_albums, prev?.distinct_albums)} />
    </div>
    <div class="row trends">
      <AreaTrend title="Listens over time" points={listensTrend} />
      <AreaTrend title="Time listened" points={timeTrend} formatValue={formatDuration} />
      <AreaTrend title="Artists over time" points={artistsTrend} />
    </div>
    <div class="row charts">
      <ListeningClock {hours} {tz} />
      <WeekdayChart {days} />
    </div>
    <div class="row tops">
      <TopList title="Top Artists" items={artists} href="{base}/artists" covers={true} />
      <TopList title="Top Tracks" items={tracks} href="{base}/tracks" />
      <TopList title="Top Albums" items={albums} href="{base}/albums" covers={true} />
    </div>
    <RecentList items={recent} {base} {tz} />
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
