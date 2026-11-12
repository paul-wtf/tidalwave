<script lang="ts">
  import { page } from '$app/stores';
  import { statsApi, type GenreDetail, type MetricPoint } from '$lib/api/client';
  import { loadDetail } from '$lib/detailLoader';
  import { rangeQuery } from '$lib/stores/range';
  import { durationStat } from '$lib/format';
  import { artistItems, type ListItem } from '$lib/listItems';
  import StatCard from './StatCard.svelte';
  import AreaTrend from './AreaTrend.svelte';
  import TopList from './TopList.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const name = $derived($page.url.searchParams.get('genre') ?? '');

  let detail = $state<GenreDetail | null>(null);
  let metrics = $state<MetricPoint[]>([]);
  let artists = $state<ListItem[]>([]);
  let notFound = $state(false);
  let error = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const q = shared ? undefined : $rangeQuery;
    const params = q?.params;
    const bucket = q?.bucket ?? 'day';
    const genre = name;
    return loadDetail(
      shared,
      () => Promise.all([
        client.genre(genre, params),
        client.metricsOverTime(bucket, { ...params, genre }),
        client.topArtists(100, { ...params, genre })
      ]),
      ([d, m, a]) => {
        detail = d; metrics = m;
        artists = artistItems(a, base);
      },
      (st) => {
        notFound = st === 'notFound';
        error = st === 'error';
        if (st === 'notFound') detail = null;
      }
    );
  });

  const trend = $derived(metrics.map((m) => ({ period: m.period, value: m.listens })));
  const time = $derived(detail ? durationStat(detail.listens, detail.seconds) : null);
</script>

{#if notFound}
  <p class="msg">Nothing found for {name}.</p>
{:else if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if detail && time}
  <div class="dashboard">
    <header>
      <p class="eyebrow">genre</p>
      <h1>{detail.genre}</h1>
    </header>
    <div class="row stats">
      <StatCard label="Listens" value={detail.listens} />
      <StatCard label="Time listened" value={time.value} format={time.format} sub={time.sub} />
      <StatCard label="Artists" value={detail.artists} />
    </div>
    <AreaTrend title="Listens over time" points={trend} />
    <TopList title="Top Artists" items={artists} initial={100} covers={true} />
  </div>
{/if}

<style>
  header {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .eyebrow {
    margin: 0;
  }
  h1 {
    margin: 0;
    font-size: 2rem;
    overflow-wrap: anywhere;
  }
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
