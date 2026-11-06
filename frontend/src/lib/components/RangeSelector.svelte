<script lang="ts">
  import { range, ROLLING, CALENDAR, type RangeSel } from '$lib/stores/range';

  const CUSTOM = 'custom';
  let from = $state('');
  let to = $state('');
  let custom = $state($range.kind === 'custom');

  const value = $derived(custom ? CUSTOM : `${$range.kind}:${'key' in $range ? $range.key : ''}`);

  $effect(() => {
    if ($range.kind === 'custom') {
      from = $range.from;
      to = $range.to;
    }
  });

  function choose(e: Event) {
    const v = (e.currentTarget as HTMLSelectElement).value;
    if (v === CUSTOM) {
      custom = true;
      return;
    }
    custom = false;
    const [kind, key] = v.split(':');
    range.set({ kind, key } as RangeSel);
  }

  const valid = $derived(from !== '' && to !== '' && from <= to);

  function apply() {
    if (valid) range.set({ kind: 'custom', from, to });
  }
</script>

<div class="ranges">
  <select aria-label="Time range" {value} onchange={choose}>
    <optgroup label="Rolling">
      {#each ROLLING as r (r.key)}
        <option value="rolling:{r.key}">{r.label}</option>
      {/each}
    </optgroup>
    <optgroup label="Calendar">
      {#each CALENDAR as r (r.key)}
        <option value="calendar:{r.key}">{r.label}</option>
      {/each}
    </optgroup>
    <optgroup label="Custom">
      <option value={CUSTOM}>Custom…</option>
    </optgroup>
  </select>
  {#if custom}
    <input type="date" aria-label="From" bind:value={from} max={to || undefined} />
    <input type="date" aria-label="To" bind:value={to} min={from || undefined} />
    <button type="button" disabled={!valid} onclick={apply}>Apply</button>
  {/if}
</div>

<style>
  .ranges {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
  }
  select,
  input,
  button {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    padding: 0.32rem 0.6rem;
    border-radius: var(--r-xs);
    border: 1px solid var(--surface0);
    background: var(--surface0);
    color: var(--text);
  }
  button {
    cursor: pointer;
    background: var(--accent-text);
    color: var(--accent-contrast);
    border-color: var(--accent-text);
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
