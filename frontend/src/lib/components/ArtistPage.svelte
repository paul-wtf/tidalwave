<script lang="ts">
  import { page } from '$app/stores';
  import {
    statsApi, ApiError,
    type ArtistDetail, type MetricPoint, type RecentItem
  } from '$lib/api/client';
  import { auth, loadMe } from '$lib/stores/auth';
  import { rangeQuery } from '$lib/stores/range';
  import { formatCount, formatDuration, formatLocalDate } from '$lib/format';
  import { trackItems, albumItems, type ListItem } from '$lib/listItems';
  import DetailHeader from './DetailHeader.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';
  import RecentList from './RecentList.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const name = $derived($page.url.searchParams.get('artist') ?? '');
  const tz = $derived(token ? 'UTC' : ($auth.user?.timezone ?? 'UTC'));

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
    let stale = false;
    (async () => {
      try {
        const [d, m, tr, al, rc] = await Promise.all([
          client.artist(artist, params),
          client.metricsOverTime(bucket, { ...params, artist }),
          client.topTracks(10, { ...params, artist }),
          client.topAlbums(10, { ...params, artist }),
          client.recent(12, { ...params, artist })
        ]);
        if (stale) return;
        detail = d; metrics = m; recent = rc;
        tracks = trackItems(tr, base);
        albums = albumItems(al, base);
        notFound = false; error = false;
      } catch (e) {
        if (stale) return;
        if (e instanceof ApiError && e.status === 404) { detail = null; notFound = true; error = false; }
        else if (!shared && e instanceof ApiError && e.status === 401) await loadMe();
        else error = true;
      }
    })();
    return () => { stale = true; };
  });

  const trend = $derived(metrics.map((m) => ({ period: m.period, value: m.listens })));
</script>

{#if notFound}
  <p class="msg">Nothing found for {name}.</p>
{:else if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if detail}
  <div class="page">
    <DetailHeader
      title={detail.artist}
      query={detail.artist}
      image={detail.image_url}
      stats={[
        { label: 'Listens', value: formatCount(detail.listens) },
        { label: 'Time listened', value: formatDuration(detail.seconds) },
        { label: 'Rank', value: detail.rank == null ? '–' : `#${formatCount(detail.rank)}` },
        { label: 'First listen', value: formatLocalDate(detail.first_listen, tz) },
        { label: 'Last listen', value: formatLocalDate(detail.last_listen, tz) }
      ]}
    />
    <AreaTrend title="Listens over time" points={trend} />
    <div class="row">
      <TopList title="Top Tracks" items={tracks} />
      <TopList title="Top Albums" items={albums} covers={true} />
    </div>
    <RecentList items={recent} {base} />
  </div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
    gap: 1.5rem;
  }
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
