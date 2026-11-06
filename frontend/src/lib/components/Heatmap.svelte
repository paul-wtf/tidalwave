<script lang="ts">
  import type { Heatmap } from '$lib/api/client';

  let { heatmap }: { heatmap: Heatmap } = $props();

  const CELL = 12;
  const STEP = 14;
  const DAY_MS = 86_400_000;

  const utc = (s: string) => {
    const [y, m, d] = s.split('-').map(Number);
    return Date.UTC(y, m - 1, d);
  };
  const mondayIndex = (ms: number) => (new Date(ms).getUTCDay() + 6) % 7;
  const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);

  const cells = $derived.by(() => {
    const counts = new Map(heatmap.days.map((d) => [d.date, d.listens]));
    const first = utc(heatmap.start);
    const last = utc(heatmap.end);
    const offset = mondayIndex(first);
    const max = Math.max(0, ...counts.values());
    const out: { date: string; listens: number; level: number; col: number; row: number }[] = [];
    for (let t = first, i = 0; t <= last; t += DAY_MS, i++) {
      const date = iso(t);
      const listens = counts.get(date) ?? 0;
      const level = listens === 0 ? 0 : Math.min(4, Math.ceil((listens / max) * 4));
      out.push({ date, listens, level, col: Math.floor((i + offset) / 7), row: (i + offset) % 7 });
    }
    return out;
  });
  const columns = $derived(cells.length ? cells[cells.length - 1].col + 1 : 0);
</script>

<section class="glass">
  <h2>Listening heatmap</h2>
  <div class="scroll">
    <svg
      role="img"
      aria-label="Listens per day, {heatmap.start} to {heatmap.end}"
      width="100%"
      style="min-width: {columns * STEP}px; max-width: {columns * STEP * 2}px"
      viewBox="0 0 {columns * STEP} {7 * STEP}"
    >
      {#each cells as c (c.date)}
        <rect
          class="l{c.level}"
          data-level={c.level}
          x={c.col * STEP}
          y={c.row * STEP}
          width={CELL}
          height={CELL}
          rx="2"
        >
          <title>{`${c.date}: ${c.listens} ${c.listens === 1 ? 'listen' : 'listens'}`}</title>
        </rect>
      {/each}
    </svg>
  </div>
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
  .scroll {
    overflow-x: auto;
  }
  svg {
    display: block;
    height: auto;
  }
  .l0 {
    fill: var(--surface0);
  }
  .l1 {
    fill: color-mix(in srgb, var(--accent) 25%, var(--surface0));
  }
  .l2 {
    fill: color-mix(in srgb, var(--accent) 50%, var(--surface0));
  }
  .l3 {
    fill: color-mix(in srgb, var(--accent) 75%, var(--surface0));
  }
  .l4 {
    fill: var(--accent);
  }
</style>
