<script lang="ts">
  import {
    statsApi,
    type Discoveries as DiscoveriesData, type Genres as GenresData, type Heatmap as HeatmapData,
    type Milestones as MilestonesData,
    type OnThisDayYear, type Records as RecordsData
  } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { loadDetail } from '$lib/detailLoader';
  import { range, rangeQuery } from '$lib/stores/range';
  import OnThisDay from './OnThisDay.svelte';
  import Records from './Records.svelte';
  import Milestones from './Milestones.svelte';
  import Heatmap from './Heatmap.svelte';
  import HourWeekdayGrid from './HourWeekdayGrid.svelte';
  import Discoveries from './Discoveries.svelte';
  import Genres from './Genres.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));
  const allTime = $derived(!token && $range.kind === 'rolling' && $range.key === 'all');

  let onThisDay = $state<OnThisDayYear[]>([]);
  let records = $state<RecordsData | null>(null);
  let milestones = $state<MilestonesData | null>(null);
  let heatmap = $state<HeatmapData | null>(null);
  let hourWeekday = $state<number[][]>([]);
  let discoveries = $state<DiscoveriesData | null>(null);
  let genres = $state<GenresData | null>(null);
  let error = $state(false);

  $effect(() => {
    const shared = token != null;
    const client = statsApi(token);
    const params = shared ? undefined : $rangeQuery.params;
    const skipDiscoveries = allTime;
    return loadDetail(
      shared,
      () => Promise.all([
        client.onThisDay(),
        client.records(params),
        shared ? Promise.resolve(null) : client.milestones(),
        client.heatmap(params),
        client.hourWeekday(params),
        skipDiscoveries ? Promise.resolve(null) : client.discoveries(params),
        client.genres(10, params)
      ]),
      ([o, r, m, h, g, d, ge]) => {
        onThisDay = o; records = r; milestones = m; heatmap = h; hourWeekday = g; discoveries = d;
        genres = ge;
      },
      (st) => (error = st !== 'ok')
    );
  });
</script>

{#if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if records && heatmap}
  <div class="dashboard">
    <OnThisDay years={onThisDay} {base} />
    <Records {records} {tz} />
    {#if milestones}<Milestones {milestones} {base} {tz} />{/if}
    <Heatmap {heatmap} />
    <HourWeekdayGrid grid={hourWeekday} {tz} />
    {#if genres}<Genres {genres} {base} />{/if}
    {#if allTime}
      <section class="glass">
        <h2>Discoveries</h2>
        <p class="empty">Pick a range to see discoveries.</p>
      </section>
    {:else if discoveries}
      <Discoveries {discoveries} {base} {tz} />
    {/if}
  </div>
{/if}

<style>
  section {
    padding: 1.4rem 1.5rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
    margin: 0 0 1rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
