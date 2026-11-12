<script lang="ts">
  import { page } from '$app/stores';
  import {
    statsApi,  type AlbumDetail, type MetricPoint
  } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { loadDetail } from '$lib/detailLoader';
  import { rangeQuery } from '$lib/stores/range';
  import { durationStat, formatLongDate } from '$lib/format';
  import { artistHref } from '$lib/links';
  import { trackItems, type ListItem } from '$lib/listItems';
  import DetailHeader from './DetailHeader.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const artistName = $derived($page.url.searchParams.get('artist') ?? '');
  const albumName = $derived($page.url.searchParams.get('album') ?? '');
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));

  let detail = $state<AlbumDetail | null>(null);
  let metrics = $state<MetricPoint[]>([]);
  let tracks = $state<ListItem[]>([]);
  let notFound = $state(false);
  let error = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    const artist = artistName;
    const album = albumName;
    return loadDetail(
      shared,
      () => Promise.all([
        client.album(artist, album, params),
        client.metricsOverTime(bucket, { ...params, artist, album }),
        client.topTracks(100, { ...params, artist, album })
      ]),
      ([d, m, tr]) => {
        detail = d; metrics = m;
        tracks = trackItems(tr, base);
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
  <p class="msg">Nothing found for {albumName}.</p>
{:else if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if detail}
  <div class="dashboard">
    <DetailHeader
      title={detail.album}
      query={`${detail.artist} ${detail.album}`}
      image={detail.image_url}
      stats={[
        { label: 'Listens', value: detail.listens },
        { label: 'Time listened', ...durationStat(detail.listens, detail.seconds) },
        { label: 'First listen', value: formatLongDate(detail.first_listen, tz), compact: true },
        { label: 'Last listen', value: formatLongDate(detail.last_listen, tz), compact: true }
      ]}
    >
      {#snippet links()}
        <a href={artistHref(base, detail!.artist)}>{detail!.artist}</a>
      {/snippet}
      <AreaTrend title="Listens over time" points={trend} />
    </DetailHeader>
    <TopList title="Tracks" items={tracks} initial={100} />
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
