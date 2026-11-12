<script lang="ts">
  import { formatCount, weekdayName } from '$lib/format';

  let { grid, tz = 'UTC' }: { grid: number[][]; tz?: string | null } = $props();

  const HOUR_LABELS = [0, 6, 12, 18, 23];
  const slot = (day: number, hour: number) => `${weekdayName(day)} ${String(hour).padStart(2, '0')}:00`;
  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;

  const max = $derived(Math.max(0, ...grid.flat()));
  const total = $derived(grid.flat().reduce((a, b) => a + b, 0));
  const rows = $derived(
    grid.map((hours, day) => hours.map((count, hour) => ({
      count,
      title: `${slot(day, hour)}: ${listens(count)}`,
      level: count === 0 ? 0 : Math.min(4, Math.ceil((count / max) * 4))
    })))
  );
  const summary = $derived.by(() => {
    if (max === 0) return listens(total);
    const day = grid.findIndex((hours) => hours.includes(max));
    return `${listens(total)} · busiest ${slot(day, grid[day].indexOf(max))} with ${formatCount(max)}`;
  });
</script>

<section class="glass">
  <h2>By weekday and hour ({tz ?? 'local time'})</h2>
  <div class="grid" role="img" aria-label="Listens by weekday and hour of day">
    {#each rows as cells, day (day)}
      <span class="day" aria-hidden="true">{weekdayName(day)}</span>
      {#each cells as c, hour (hour)}
        <span class="cell l{c.level}" data-level={c.level} title={c.title}></span>
      {/each}
    {/each}
    <span></span>
    {#each { length: 24 } as _, hour (hour)}
      <span class="hour" aria-hidden="true">{HOUR_LABELS.includes(hour) ? hour : ''}</span>
    {/each}
  </div>
  <span class="sr-only">{summary}</span>
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
  .grid {
    display: grid;
    grid-template-columns: auto repeat(24, minmax(0, 1fr));
    gap: 3px;
    align-items: center;
  }
  .day,
  .hour {
    font-family: var(--font-mono);
    font-size: 0.64rem;
    color: var(--overlay2);
  }
  .day {
    padding-right: 0.5rem;
  }
  .hour {
    text-align: center;
    margin-top: 0.3rem;
  }
  .cell {
    height: 1.35rem;
    border-radius: 3px;
  }
  .l0 {
    background: var(--surface0);
  }
  .l1 {
    background: color-mix(in srgb, var(--accent) 25%, var(--surface0));
  }
  .l2 {
    background: color-mix(in srgb, var(--accent) 50%, var(--surface0));
  }
  .l3 {
    background: color-mix(in srgb, var(--accent) 75%, var(--surface0));
  }
  .l4 {
    background: var(--accent);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
</style>
