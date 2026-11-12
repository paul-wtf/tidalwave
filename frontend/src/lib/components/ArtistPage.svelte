<script lang="ts">
  import { page } from '$app/stores';
  import {
    statsApi,
    type ArtistDetail, type MetricPoint, type RecentItem
  } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { loadDetail } from '$lib/detailLoader';
  import { rangeQuery } from '$lib/stores/range';
  import { formatCount, durationStat, formatLongDate } from '$lib/format';
  import { trackItems, albumItems, type ListItem } from '$lib/listItems';
  import DetailHeader from './DetailHeader.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';
  import RecentList from './RecentList.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const name = $derived($page.url.searchParams.get('artist') ?? '');
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));

  let detail = $state<ArtistDetail | null>(null);
  let metrics = $state<MetricPoint[]>([]);
  let tracks = $state<ListItem[]>([]);
  let albums = $state<ListItem[]>([]);
  let recent = $state<RecentItem[]>([]);
  let notFound = $state(false);
  let error = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    const artist = name;
    return loadDetail(
      shared,
      () => Promise.all([
        client.artist(artist, params),
        client.metricsOverTime(bucket, { ...params, artist }),
        client.topTracks(10, { ...params, artist }),
        client.topAlbums(10, { ...params, artist }),
        client.recent(12, { ...params, artist })
      ]),
      ([d, m, tr, al, rc]) => {
        detail = d; metrics = m; recent = rc;
        tracks = trackItems(tr, base);
        albums = albumItems(al, base);
      },
      (st) => {
        notFound = st === 'notFound';
        error = st === 'error';
        if (st === 'notFound') detail = null;
      }
    );
  });

  const trend = $derived(metrics.map((m) => ({ period: m.period, value: m.listens })));
</script>

{#if notFound}
  <p class="msg">Nothing found for {name}.</p>
{:else if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if detail}
  <div class="dashboard">
    <DetailHeader
      title={detail.artist}
      query={detail.artist}
      image={detail.image_url}
      stats={[
        { label: 'Listens', value: detail.listens },
        { label: 'Time listened', ...durationStat(detail.listens, detail.seconds) },
        { label: 'Rank', value: detail.rank == null ? '–' : `#${formatCount(detail.rank)}` },
        { label: 'First listen', value: formatLongDate(detail.first_listen, tz), compact: true },
        { label: 'Last listen', value: formatLongDate(detail.last_listen, tz), compact: true }
      ]}
    />
    <AreaTrend title="Listens over time" points={trend} />
    <div class="row charts">
      <TopList title="Top Tracks" items={tracks} />
      <TopList title="Top Albums" items={albums} covers={true} />
    </div>
    <RecentList items={recent} {base} {tz} />
  </div>
{/if}

<style>
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
