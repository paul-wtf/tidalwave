<script lang="ts">
  import type { Records } from '$lib/api/client';
  import { formatCount, formatDuration, formatLocalDate } from '$lib/format';

  let { records, tz = 'UTC' }: { records: Records; tz?: string } = $props();

  const days = (n: number) => `${formatCount(n)} ${n === 1 ? 'day' : 'days'}`;
  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;

  const items = $derived.by(() => {
    const out: { label: string; value: string; detail: string }[] = [];
    const { longest_streak: ls, current_streak: cs, busiest_day: bd, longest_session: se } = records;
    if (ls) out.push({ label: 'Longest streak', value: days(ls.days), detail: `${ls.start} to ${ls.end}` });
    if (cs) out.push({ label: 'Current streak', value: days(cs.days), detail: `since ${cs.start}` });
    if (bd) out.push({ label: 'Busiest day', value: listens(bd.listens), detail: bd.date });
    if (se) {
      out.push({
        label: 'Longest session',
        value: listens(se.listens),
        detail: `${formatLocalDate(se.start, tz)}, ${formatDuration(se.seconds)}`
      });
    }
    return out;
  });
</script>

<section class="glass">
  <h2>Streaks and records</h2>
  {#if items.length === 0}
    <p class="empty">No records in this range yet.</p>
  {:else}
    <dl>
      {#each items as item (item.label)}
        <div class="item">
          <dt>{item.label}</dt>
          <dd class="value">{item.value}</dd>
          <dd class="detail">{item.detail}</dd>
        </div>
      {/each}
    </dl>
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
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 1.25rem;
  }
  dd {
    margin: 0;
  }
  dt {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .value {
    font-size: 1.4rem;
    color: var(--text);
  }
  .detail {
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
