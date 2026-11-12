<script lang="ts">
  import { untrack } from 'svelte';
  import { formatCount } from '$lib/format';
  import { prefersReducedMotion, tween } from '$lib/motion';

  let { label, value, format = formatCount, sub, delta, compact = false }: {
    label: string;
    value: string | number;
    format?: (n: number) => string;
    sub?: string;
    delta?: number | null;
    compact?: boolean;
  } = $props();

  let shown = $state(untrack(() => (typeof value === 'number' && prefersReducedMotion() ? value : 0)));

  $effect(() => {
    if (typeof value !== 'number') return;
    return tween(untrack(() => shown), value, (v) => (shown = v));
  });

  const display = $derived(typeof value === 'number' ? format(Math.round(shown)) : value);

  const pct = $derived(delta == null ? null : Math.round(delta * 100));
  const dir = $derived(pct == null ? null : pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat');
  const text = $derived(
    pct == null ? '' : pct > 0 ? `+${pct} %` : pct < 0 ? `−${-pct} %` : '±0 %'
  );
  const aria = $derived(
    pct == null ? '' :
    pct > 0 ? `${pct} % more than the previous period` :
    pct < 0 ? `${-pct} % less than the previous period` :
    'No change from the previous period'
  );
</script>

<div class="stat glass">
  <span class="value" class:compact>{display}</span>
  <span class="label">{label}</span>
  {#if dir}<span class="delta {dir}" aria-label={aria}>{text} vs. previous</span>{/if}
  {#if sub}<span class="sub">{sub}</span>{/if}
</div>

<style>
  .stat {
    padding: 1.25rem 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .value {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(2rem, 5vw, 2.85rem);
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }
  .value.compact {
    font-size: clamp(1.15rem, 2.4vw, 1.4rem);
    line-height: 1.2;
    white-space: nowrap;
  }
  .label {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    text-transform: lowercase;
    color: var(--text-muted);
  }
  .delta {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }
  .delta.up { color: var(--green); }
  .delta.down { color: var(--red); }
  .delta.flat { color: var(--text-muted); }
  .sub {
    font-size: 0.8rem;
    color: var(--text-dim);
  }
</style>
