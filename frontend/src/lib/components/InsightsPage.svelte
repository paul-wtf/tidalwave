<script lang="ts">
  import {
    statsApi,
    type Discoveries as DiscoveriesData, type Heatmap as HeatmapData,
    type OnThisDayYear, type Records as RecordsData
  } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { loadDetail } from '$lib/detailLoader';
  import { range, rangeQuery } from '$lib/stores/range';
  import OnThisDay from './OnThisDay.svelte';
  import Records from './Records.svelte';
  import Heatmap from './Heatmap.svelte';
  import Discoveries from './Discoveries.svelte';

  let { token }: { token?: string } = $props();

  const base = $derived(token ? `/s/${token}` : '');
  const tz = $derived(token ? 'UTC' : ($auth.user?.timezone ?? 'UTC'));
  const allTime = $derived(!token && $range.kind === 'rolling' && $range.key === 'all');

  let onThisDay = $state<OnThisDayYear[]>([]);
  let records = $state<RecordsData | null>(null);
  let heatmap = $state<HeatmapData | null>(null);
  let discoveries = $state<DiscoveriesData | null>(null);
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
        client.heatmap(params),
        skipDiscoveries ? Promise.resolve(null) : client.discoveries(params)
      ]),
      ([o, r, h, d]) => {
        onThisDay = o; records = r; heatmap = h; discoveries = d;
      },
      (st) => (error = st !== 'ok')
    );
  });
</script>

{#if error}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if records && heatmap}
  <div class="page">
    <OnThisDay years={onThisDay} {base} />
    <Records {records} {tz} />
    <Heatmap {heatmap} />
    {#if discoveries}
      <Discoveries {discoveries} {base} {tz} />
    {/if}
  </div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
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
