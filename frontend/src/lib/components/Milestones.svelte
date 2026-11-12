<script lang="ts">
  import type { Milestones } from '$lib/api/client';
  import { formatCount, formatLongDate } from '$lib/format';
  import { artistHref, trackHref } from '$lib/links';

  let { milestones, base = '', tz = 'UTC' }:
    { milestones: Milestones; base?: string; tz?: string | null } = $props();

  const next = $derived(milestones.next);
</script>

<section class="glass">
  <h2>Milestones</h2>
  {#if milestones.reached.length > 0}
    <dl>
      {#each milestones.reached as m (m.count)}
        <div class="item">
          <dt>{formatCount(m.count)}th listen</dt>
          <dd class="value"><a href={trackHref(base, m.artist, m.track)}>{m.track}</a></dd>
          <dd class="detail">
            <a href={artistHref(base, m.artist)}>{m.artist}</a>
            <span>{formatLongDate(m.played_at, tz)}</span>
          </dd>
        </div>
      {/each}
    </dl>
  {/if}
  {#if next}
    <p class="next">
      {formatCount(next.remaining)} {next.remaining === 1 ? 'listen' : 'listens'} to go until {formatCount(next.count)}
    </p>
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
    font-size: 1.15rem;
    color: var(--text);
    overflow-wrap: anywhere;
  }
  .detail {
    display: flex;
    flex-wrap: wrap;
    gap: 0 0.6rem;
    color: var(--text-dim);
    font-size: 0.8rem;
  }
  .detail span {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }
  a {
    color: inherit;
    text-decoration: none;
  }
  a:hover {
    color: var(--accent-text);
  }
  .next {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  dl + .next {
    margin-top: 1.1rem;
  }
</style>
