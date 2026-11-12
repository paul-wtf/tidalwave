<script lang="ts">
  import { range, ROLLING, CALENDAR, type RangeSel } from '$lib/stores/range';

  const CUSTOM = 'custom';
  const CURRENT = 'custom:current';
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  let from = $state('');
  let to = $state('');
  let editing = $state(false);
  let root: HTMLDivElement | undefined = $state();

  const active = $derived($range.kind === 'custom' ? $range : null);
  const value = $derived(
    editing ? CUSTOM : active ? CURRENT : `${$range.kind}:${'key' in $range ? $range.key : ''}`
  );

  function day(iso: string): [string, number] {
    const [, m, d] = iso.split('-').map(Number);
    return [MONTHS[m - 1], d];
  }

  const activeLabel = $derived.by(() => {
    if (!active) return '';
    const [fm, fd] = day(active.from);
    const [tm, td] = day(active.to);
    return fm === tm && active.from.slice(0, 4) === active.to.slice(0, 4)
      ? `${fm} ${fd}–${td}`
      : `${fm} ${fd}–${tm} ${td}`;
  });

  function choose(e: Event) {
    const select = e.currentTarget as HTMLSelectElement;
    const v = select.value;
    if (v === CURRENT) return;
    if (v === CUSTOM) {
      from = active?.from ?? '';
      to = active?.to ?? '';
      editing = true;
      return;
    }
    editing = false;
    const [kind, key] = v.split(':');
    range.set({ kind, key } as RangeSel);
  }

  const valid = $derived(from !== '' && to !== '' && from <= to);

  function apply() {
    if (!valid) return;
    range.set({ kind: 'custom', from, to });
    editing = false;
  }

  function onWindowClick(e: MouseEvent) {
    if (editing && root && !e.composedPath().includes(root)) editing = false;
  }

  function onWindowKey(e: KeyboardEvent) {
    if (editing && e.key === 'Escape') editing = false;
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<div class="ranges" bind:this={root}>
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
      {#if active}<option value={CURRENT}>{activeLabel}</option>{/if}
      <option value={CUSTOM}>Custom…</option>
    </optgroup>
  </select>
  {#if editing}
    <div class="panel" role="group" aria-label="Custom range">
      <label>
        <span>From</span>
        <input type="date" bind:value={from} max={to || undefined} />
      </label>
      <label>
        <span>To</span>
        <input type="date" bind:value={to} min={from || undefined} />
      </label>
      <div class="row">
        <button type="button" class="ghost" onclick={() => (editing = false)}>Cancel</button>
        <button type="button" disabled={!valid} onclick={apply}>Apply</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .ranges {
    display: inline-flex;
    align-items: center;
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
  .panel {
    position: fixed;
    top: var(--bar-h);
    right: clamp(1rem, 4vw, 2rem);
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    width: 15rem;
    max-width: calc(100vw - 2rem);
    padding: 0.85rem;
    background: var(--surface0);
    border-radius: var(--r-sm);
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .panel input {
    background: var(--surface1);
    border-color: var(--surface1);
  }
  input:focus-visible,
  select:focus-visible,
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .row {
    display: flex;
    justify-content: flex-end;
    gap: 0.4rem;
  }
  button {
    cursor: pointer;
    background: var(--accent-text);
    color: var(--accent-contrast);
    border-color: var(--accent-text);
  }
  button.ghost {
    background: transparent;
    color: var(--text-muted);
    border-color: transparent;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
