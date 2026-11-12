<script lang="ts">
  import { formatCount } from '$lib/format';
  import { dialPoint, dialSector } from '$lib/dial';

  let { hours, tz = 'UTC' }: { hours: number[]; tz?: string | null } = $props();

  const INNER = 34;
  const OUTER = 84;
  const MARKS = [0, 6, 12, 18];

  const clock = (h: number) => `${String(h).padStart(2, '0')}:00`;
  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;

  const total = $derived(hours.reduce((a, b) => a + b, 0));
  const max = $derived(Math.max(0, ...hours));
  const peak = $derived(max > 0 ? hours.indexOf(max) : null);
  const segments = $derived(
    hours.map((count, h) => {
      const reach = max > 0 ? count / max : 0;
      return {
        h,
        reach,
        text: `${clock(h)}: ${listens(count)}`,
        track: dialSector(h, INNER, OUTER),
        bar: reach > 0 ? dialSector(h, INNER, INNER + Math.max(reach * (OUTER - INNER), 2)) : ''
      };
    })
  );
  const marks = MARKS.map((h) => {
    const [x, y] = dialPoint(h, OUTER + 9);
    return { label: String(h).padStart(2, '0'), x: Math.round(x * 100) / 100 || 0, y: Math.round(y * 100) / 100 || 0 };
  });
</script>

<figure class="glass">
  <figcaption>By hour ({tz ?? 'local time'})</figcaption>
  <svg viewBox="-100 -100 200 200" role="img" aria-label="Listens by hour of day on a 24-hour dial">
    {#each segments as s (s.h)}
      <path class="track" d={s.track} />
      <path class="seg" data-hour={s.h} data-reach={s.reach} d={s.bar}><title>{s.text}</title></path>
    {/each}
    {#each marks as m (m.label)}
      <text class="mark" x={m.x} y={m.y}>{m.label}</text>
    {/each}
    {#if peak !== null}
      <text class="peak" x="0" y="-1">{clock(peak)}</text>
      <text class="peak-label" x="0" y="11">peak</text>
    {/if}
  </svg>
  <div class="sr-only">
    <p>{peak === null ? listens(total) : `${listens(total)} · peak ${clock(peak)} with ${formatCount(max)}`}</p>
    <ol>
      {#each segments as s (s.h)}<li>{s.text}</li>{/each}
    </ol>
  </div>
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
  svg {
    display: block;
    width: 100%;
    height: 250px;
  }
  .track {
    fill: var(--surface0);
  }
  /* The clock is the one element in this app that gets the sky accent
     (see zen colour discipline — sky is reserved for exactly one
     special element). */
  .seg {
    fill: var(--accent-cyan);
    transition: filter var(--dur-fast) var(--ease-out);
  }
  .seg:hover {
    filter: brightness(1.18);
  }
  text {
    text-anchor: middle;
    dominant-baseline: middle;
    font-family: var(--font-mono);
  }
  .mark,
  .peak-label {
    font-size: 7.5px;
    fill: var(--overlay2);
  }
  .peak {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 15px;
    fill: var(--text);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
</style>
