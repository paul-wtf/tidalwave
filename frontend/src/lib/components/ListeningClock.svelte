<script lang="ts">
  let { hours, tz = 'UTC' }: { hours: number[]; tz?: string | null } = $props();
  const total = $derived(hours.reduce((a, b) => a + b, 0));
  const max = $derived(Math.max(1, ...hours));
</script>

<figure class="glass" role="img" aria-label="Listens by hour of day">
  <figcaption>By hour ({tz ?? 'local time'})</figcaption>
  <div class="plot">
    <div class="yaxis" aria-hidden="true">
      <span>{max}</span>
      <span>{Math.round(max / 2)}</span>
      <span>0</span>
    </div>
    <div class="plot-main">
      <div class="barchart clock" aria-hidden="true">
        {#each hours as count, h (h)}
          <div class="col" title="{h}:00 — {count}">
            <div class="bar" style="height: {(count / max) * 100}%"></div>
          </div>
        {/each}
      </div>
      <div class="barlabels" aria-hidden="true">
        <span>0</span><span>6</span><span>12</span><span>18</span><span>23</span>
      </div>
    </div>
  </div>
  <span class="sr-only">{total} listens · peak {max} per hour</span>
</figure>

<style>
  figure {
    padding: 1.4rem 1.5rem;
    margin: 0;
  }
  figcaption {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.35rem;
    color: var(--text);
    margin-bottom: 0.9rem;
  }
  /* The clock is the one element in this app that gets the sky accent
     (see zen colour discipline — sky is reserved for exactly one
     special element). */
  .clock :global(.col .bar) {
    background: var(--accent-cyan);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
</style>
