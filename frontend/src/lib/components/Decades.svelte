<script lang="ts">
  import type { Decades } from '$lib/api/client';
  import { formatCount } from '$lib/format';

  let { decades }: { decades: Decades } = $props();

  const total = $derived(decades.known + decades.unknown);
  const max = $derived(Math.max(1, ...decades.decades.map((d) => d.listens)));
  const pct = (n: number) => Math.round((n / total) * 100);

  const coverage = $derived.by(() => {
    if (decades.unknown === 0) return 'Covers all listens in this range.';
    const covered =
      `Covers ${pct(decades.known)} % of the listens in this range ` +
      `(${formatCount(decades.known)} of ${formatCount(total)}).`;
    return decades.pending > 0
      ? `${covered} Release years for another ${pct(decades.pending)} % are still being looked up.`
      : `${covered} The rest has no known release year.`;
  });
</script>

<section class="glass">
  <h2>By decade</h2>
  {#if total === 0}
    <p class="empty">No data yet.</p>
  {:else if decades.known === 0}
    <p class="empty">
      {decades.pending > 0
        ? 'Release years are still being looked up on MusicBrainz.'
        : 'No release years are known for the listens in this range.'}
    </p>
  {:else}
    <div class="plot" role="img" aria-label="Listens by release decade">
      <div class="yaxis" aria-hidden="true">
        <span>{formatCount(max)}</span>
        <span>{formatCount(Math.round(max / 2))}</span>
        <span>0</span>
      </div>
      <div class="plot-main">
        <div class="barchart">
          {#each decades.decades as d (d.decade)}
            <div class="col" title="{d.decade}s: {formatCount(d.listens)} {d.listens === 1 ? 'listen' : 'listens'}">
              <div class="bar" style="height: {(d.listens / max) * 100}%"></div>
            </div>
          {/each}
        </div>
        <div class="barlabels even" aria-hidden="true">
          {#each decades.decades as d (d.decade)}<span>{d.decade}s</span>{/each}
        </div>
      </div>
    </div>
    <p class="note">{coverage}</p>
  {/if}
</section>

<style>
  section {
    padding: 1.4rem 1.5rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
    margin: 0 0 1rem;
  }
  .note {
    margin: 1rem 0 0;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
