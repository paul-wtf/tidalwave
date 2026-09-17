<script lang="ts">
  import { formatDate } from '$lib/format';
  import type { Bucket } from '$lib/api/client';

  let {
    title,
    points,
    bucket,
    onBucketChange,
    formatValue = (n: number) => n.toLocaleString()
  }: {
    title: string;
    points: { period: string; value: number }[];
    bucket?: Bucket;
    onBucketChange?: (b: Bucket) => void;
    formatValue?: (n: number) => string;
  } = $props();

  // Unique per instance: three AreaTrend charts share one page, and SVG
  // gradient ids must be unique or url(#...) refs collide.
  const instanceId = $props.id();
  const gradientId = `area-fade-${instanceId}`;

  const max = $derived(Math.max(1, ...points.map((p) => p.value)));

  // Map points into a 0..100 viewBox; y is inverted (0 = top, 100 = baseline).
  const coords = $derived(
    points.map((p, i) => ({
      x: points.length > 1 ? (i / (points.length - 1)) * 100 : 50,
      y: 100 - (p.value / max) * 100,
      point: p
    }))
  );
  const linePath = $derived(
    coords.length ? 'M' + coords.map((c) => `${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(' L') : ''
  );
  const areaPath = $derived(coords.length ? `${linePath} L100,100 L0,100 Z` : '');

  const xLabels = $derived.by(() => {
    const n = points.length;
    if (n === 0) return [];
    const idx = [...new Set([0, 1 / 3, 2 / 3, 1].map((f) => Math.round(f * (n - 1))))];
    return idx.map((i) => formatDate(points[i].period));
  });

  function onChange(e: Event) {
    onBucketChange?.((e.currentTarget as HTMLSelectElement).value as Bucket);
  }
</script>

<figure class="glass" role="img" aria-label={title}>
  <figcaption class="head">
    <span class="title">{title}</span>
    {#if bucket && onBucketChange}
      <label>
        <span class="sr-only">Bucket</span>
        <select aria-label="Bucket" value={bucket} onchange={onChange}>
          <option value="day">Daily</option>
          <option value="week">Weekly</option>
          <option value="month">Monthly</option>
        </select>
      </label>
    {/if}
  </figcaption>

  {#if points.length === 0}
    <p class="empty">No data yet.</p>
  {:else}
    <div class="plot">
      <div class="yaxis" aria-hidden="true">
        <span>{formatValue(max)}</span><span>{formatValue(Math.round(max / 2))}</span><span>{formatValue(0)}</span>
      </div>
      <div class="plot-main">
        <div class="areachart">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style="stop-color: var(--accent); stop-opacity: 0.25" />
                <stop offset="100%" style="stop-color: var(--accent); stop-opacity: 0" />
              </linearGradient>
            </defs>
            <path class="area" d={areaPath} fill="url(#{gradientId})" />
            <path class="line" d={linePath} vector-effect="non-scaling-stroke" />
          </svg>
          <div class="hovers">
            {#each coords as c (c.point.period)}
              <div class="hcol" title="{formatDate(c.point.period)} — {formatValue(c.point.value)}"></div>
            {/each}
          </div>
        </div>
        <div class="barlabels">
          {#each xLabels as label, i (i)}<span>{label}</span>{/each}
        </div>
      </div>
    </div>
  {/if}
</figure>

<style>
  figure {
    padding: 1.4rem 1.5rem;
    margin: 0;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.9rem;
    min-height: 1.6rem;
  }
  .title {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.35rem;
    color: var(--text);
  }
  select {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.3rem 0.8rem;
    font-family: var(--font-body);
    font-size: 0.85rem;
    cursor: pointer;
    transition: box-shadow var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out);
  }
  select:hover {
    background: var(--surface1);
  }
  select:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .areachart {
    position: relative;
    height: 190px;
    background-image:
      linear-gradient(var(--surface0), var(--surface0)),
      linear-gradient(var(--surface0), var(--surface0)),
      linear-gradient(var(--surface0), var(--surface0));
    background-size: 100% 1px;
    background-position: 0 0, 0 50%, 0 100%;
    background-repeat: no-repeat;
  }
  .areachart svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  /* Fill is set inline via the per-instance <linearGradient> above — the one
     gradient exception in the zen system: a vertical accent fade under the
     trend line (see .areachart's <defs>). */
  .line {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .hovers {
    position: absolute;
    inset: 0;
    display: flex;
  }
  .hcol {
    flex: 1 1 0;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .hcol:hover {
    background: var(--accent-soft);
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
</style>
