<script lang="ts">
  import type { OnThisDayYear } from '$lib/api/client';
  import { formatCount } from '$lib/format';
  import { artistHref, trackHref } from '$lib/links';

  let { years, base = '' }: { years: OnThisDayYear[]; base?: string } = $props();
</script>

<section class="glass">
  <h2>On this day</h2>
  {#if years.length === 0}
    <p class="empty">Nothing on this day in earlier years.</p>
  {:else}
    <ul>
      {#each years as y (y.year)}
        <li>
          <div class="head">
            <span class="year">{y.year}</span>
            <span class="count">{formatCount(y.listens)} {y.listens === 1 ? 'listen' : 'listens'}</span>
          </div>
          <ol>
            {#each y.top_tracks as t (t.track + t.artist)}
              <li>
                <a href={trackHref(base, t.artist, t.track)}>{t.track}</a>
                <a class="artist" href={artistHref(base, t.artist)}>{t.artist}</a>
              </li>
            {/each}
          </ol>
        </li>
      {/each}
    </ul>
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
  ul,
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  ul {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .head {
    display: flex;
    gap: 0.75rem;
    align-items: baseline;
    margin-bottom: 0.3rem;
  }
  .year {
    font-family: var(--font-mono);
    color: var(--accent-text);
  }
  .count {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  ol li {
    display: flex;
    gap: 0.6rem;
    padding: 0.2rem 0.6rem;
  }
  a {
    color: inherit;
    text-decoration: none;
  }
  a:hover {
    color: var(--accent-text);
  }
  .artist {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .empty {
    color: var(--text-dim);
    margin: 0;
  }
</style>
