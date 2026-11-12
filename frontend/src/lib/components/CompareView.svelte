<script lang="ts">
  import { goto } from '$app/navigation';
  import { api, ApiError, type Comparison } from '$lib/api/client';
  import { range, rangeLabel, rangeQuery } from '$lib/stores/range';
  import { formatCount } from '$lib/format';
  import { artistHref } from '$lib/links';

  let { id }: { id: number } = $props();

  let data = $state<Comparison | null>(null);
  let status = $state<'loading' | 'ok' | 'gone' | 'error'>('loading');
  let ending = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    const params = $rangeQuery.params;
    let live = true;
    api.comparison(id, params).then(
      (d) => {
        if (!live) return;
        data = d;
        status = 'ok';
      },
      (e) => {
        if (live) status = e instanceof ApiError && e.status === 404 ? 'gone' : 'error';
      }
    );
    return () => (live = false);
  });

  const partner = $derived(data?.partner ?? 'them');
  const percent = $derived(data?.overlap == null ? null : Math.round(data.overlap * 100));
  const share = (n: number, total: number) => (total > 0 ? n / total : 0);
  const widest = $derived(
    data
      ? Math.max(
          ...data.shared.map((s) =>
            Math.max(share(s.you, data!.listens.you), share(s.partner, data!.listens.partner))
          ),
          0
        )
      : 0
  );
  const width = (n: number, total: number) =>
    widest > 0 ? `${Math.max(2, (share(n, total) / widest) * 100)}%` : '0';
  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;
  const emptySide = $derived(
    data == null ? null : data.listens.you === 0 ? 'You have' : data.listens.partner === 0 ? `${partner} has` : null
  );

  async function end() {
    error = null;
    try {
      await api.endComparison(id);
      await goto('/compare');
    } catch {
      error = 'Could not end the comparison.';
    }
  }
</script>

{#if status === 'gone'}
  <p class="msg">This comparison no longer exists. <a href="/compare">Your comparisons</a></p>
{:else if status === 'error'}
  <p class="msg">Could not load this comparison. Please try again.</p>
{:else if data}
  <div class="dashboard">
    <section class="glass head">
      <div class="title">
        <p class="eyebrow">{rangeLabel($range)}</p>
        <h1>You and {partner}</h1>
        <p class="counts">
          You: {listens(data.listens.you)} · {partner}: {listens(data.listens.partner)} ·
          {formatCount(data.shared_artists)} {data.shared_artists === 1 ? 'artist' : 'artists'} in common
        </p>
      </div>
      <div class="overlap">
        {#if percent != null}
          <span class="figure">{percent}%</span>
          <span class="label">overlap</span>
        {:else}
          <span class="figure none" aria-hidden="true">–</span>
          <span class="label">{emptySide} no listens in this range.</span>
        {/if}
      </div>
      <p class="how">
        Overlap adds up, for every artist, the smaller of your two shares of listens in this
        range. 100% means the same mix of artists, 0% means no artist in common.
      </p>
    </section>

    <section class="glass" aria-labelledby="shared-heading">
      <h2 id="shared-heading">Shared artists</h2>
      {#if data.shared.length === 0}
        <p class="empty">No artist both of you played in this range.</p>
      {:else}
        <p class="legend">
          <span class="key you"></span> your share of listens
          <span class="key them"></span> {partner}'s share
        </p>
        <ol class="shared">
          {#each data.shared as s (s.artist)}
            <li aria-label={s.artist}>
              <a class="name" href={artistHref('', s.artist)}>{s.artist}</a>
              <span class="nums">you {formatCount(s.you)} · {partner} {formatCount(s.partner)}</span>
              <span class="bars" aria-hidden="true">
                <span class="bar you" style:width={width(s.you, data.listens.you)}></span>
                <span class="bar them" style:width={width(s.partner, data.listens.partner)}></span>
              </span>
            </li>
          {/each}
        </ol>
      {/if}
    </section>

    <div class="row sides">
      <section class="glass" aria-labelledby="only-you-heading">
        <h2 id="only-you-heading">Only you</h2>
        {#if data.only_you.length === 0}
          <p class="empty">{partner} played every artist you did.</p>
        {:else}
          <ol>
            {#each data.only_you as a (a.artist)}
              <li>
                <a class="name" href={artistHref('', a.artist)}>{a.artist}</a>
                <span class="nums">{formatCount(a.count)}</span>
              </li>
            {/each}
          </ol>
        {/if}
      </section>
      <section class="glass" aria-labelledby="only-them-heading">
        <h2 id="only-them-heading">Only {partner}</h2>
        {#if data.only_partner.length === 0}
          <p class="empty">You played every artist {partner} did.</p>
        {:else}
          <ol>
            {#each data.only_partner as a (a.artist)}
              <li>
                <span class="name">{a.artist}</span>
                <span class="nums">{formatCount(a.count)}</span>
              </li>
            {/each}
          </ol>
        {/if}
      </section>
    </div>

    <div class="end">
      {#if ending}
        <div class="confirm">
          <span>You and {partner} stop seeing each other's listening. To compare again, one of you sends a new invite.</span>
          <button type="button" onclick={() => (ending = false)}>Cancel</button>
          <button type="button" class="destroy" onclick={end}>End it for both of us</button>
        </div>
      {:else}
        <button type="button" class="ghost" onclick={() => (ending = true)}>End comparison</button>
      {/if}
      {#if error}<p class="error" role="alert">{error}</p>{/if}
    </div>
  </div>
{/if}

<style>
  section {
    padding: 1.4rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }
  .head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.6rem 1.5rem;
    align-items: center;
  }
  .title {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .eyebrow {
    margin: 0;
  }
  h1 {
    font-size: 1.8rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
  }
  .counts {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .overlap {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    text-align: right;
    max-width: 14rem;
  }
  .figure {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 3.2rem;
    line-height: 1;
    color: var(--accent-text);
    font-variant-numeric: tabular-nums;
  }
  .figure.none {
    color: var(--text-dim);
  }
  .label {
    font-size: 0.82rem;
    color: var(--text-muted);
  }
  .how {
    grid-column: 1 / -1;
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-dim);
    max-width: 70ch;
  }
  .legend {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .key {
    display: inline-block;
    width: 0.8rem;
    height: 0.4rem;
    border-radius: 2px;
  }
  .key.them {
    margin-left: 0.8rem;
  }
  .you {
    background: var(--accent);
  }
  .them {
    background: var(--accent-cyan);
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    padding: 0.4rem 0.6rem;
    border-radius: var(--r-xs);
  }
  li:nth-child(odd) {
    background: var(--mantle);
  }
  .shared li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.25rem 0.75rem;
  }
  .bars {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .bar {
    height: 4px;
    border-radius: 2px;
  }
  .name {
    color: var(--text);
    text-decoration: none;
    overflow-wrap: anywhere;
  }
  a.name:hover {
    color: var(--accent-text);
  }
  .nums {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-dim);
    white-space: nowrap;
  }
  .sides {
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  }
  .empty {
    margin: 0;
    color: var(--text-dim);
  }
  .end {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .confirm {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.7rem;
    padding: 0.7rem 0.9rem;
    border-radius: var(--r-sm);
    background: var(--error-soft);
    font-size: 0.85rem;
  }
  button {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    font-size: 0.82rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  button:hover {
    background: var(--surface1);
  }
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .ghost {
    color: var(--text-muted);
  }
  .destroy,
  .destroy:hover {
    background: var(--error);
    color: var(--accent-contrast);
  }
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.85rem;
  }
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
  .msg a {
    color: var(--accent-text);
  }
  @media (max-width: 640px) {
    .head {
      grid-template-columns: 1fr;
    }
    .overlap {
      align-items: flex-start;
      text-align: left;
    }
  }
</style>
