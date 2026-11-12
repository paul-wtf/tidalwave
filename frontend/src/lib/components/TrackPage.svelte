<script lang="ts">
  import { page } from '$app/stores';
  import {
    statsApi,
    type TrackDetail, type MetricPoint, type RecentItem
  } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { loadDetail } from '$lib/detailLoader';
  import { rangeQuery } from '$lib/stores/range';
  import { durationStat, formatLongDate } from '$lib/format';
  import { artistHref, albumHref } from '$lib/links';
  import DetailHeader from './DetailHeader.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import RecentList from './RecentList.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const artistName = $derived($page.url.searchParams.get('artist') ?? '');
  const trackName = $derived($page.url.searchParams.get('track') ?? '');
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));

  let detail = $state<TrackDetail | null>(null);
  let metrics = $state<MetricPoint[]>([]);
  let recent = $state<RecentItem[]>([]);
  let notFound = $state(false);
  let error = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    const artist = artistName;
    const track = trackName;
    return loadDetail(
      shared,
      () => Promise.all([
        client.track(artist, track, params),
        client.metricsOverTime(bucket, { ...params, artist, track }),
        client.recent(20, { ...params, artist, track })
      ]),
      ([d, m, rc]) => {
        detail = d; metrics = m; recent = rc;
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
  <p class="msg">Nothing found for {trackName}.</p>
{:else if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if detail}
  <div class="dashboard">
    <DetailHeader
      title={detail.track}
      query={`${detail.artist} ${detail.track}`}
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
        {#if detail!.album}
          · <a href={albumHref(base, detail!.artist, detail!.album)}>{detail!.album}</a>
        {/if}
      {/snippet}
    </DetailHeader>
    <AreaTrend title="Listens over time" points={trend} />
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
