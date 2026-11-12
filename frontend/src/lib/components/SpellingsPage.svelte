<script lang="ts">
  import { api, type Spellings, type SpellingSuggestion } from '$lib/api/client';
  import { formatCount } from '$lib/format';

  let data = $state<Spellings | null>(null);
  let status = $state<'loading' | 'ok' | 'error'>('loading');
  let error = $state<string | null>(null);
  let busy = $state(false);
  let keep = $state<Record<string, string>>({});
  let left = $state<Record<string, string[]>>({});
  let variant = $state('');
  let canonical = $state('');

  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;
  const id = (s: SpellingSuggestion) => s.names[0].artist;
  const kept = (s: SpellingSuggestion) => keep[id(s)] ?? s.names[0].artist;
  const included = (s: SpellingSuggestion, name: string) => !(left[id(s)] ?? []).includes(name);

  async function load() {
    try {
      data = await api.spellings();
      status = 'ok';
    } catch {
      status = 'error';
    }
  }

  $effect(() => {
    void load();
  });

  async function apply(call: () => Promise<Spellings>, failure: string) {
    busy = true;
    error = null;
    try {
      data = await call();
    } catch {
      error = failure;
    } finally {
      busy = false;
    }
  }

  function toggle(s: SpellingSuggestion, name: string) {
    const current = left[id(s)] ?? [];
    left[id(s)] = current.includes(name) ? current.filter((n) => n !== name) : [...current, name];
  }

  function accept(s: SpellingSuggestion) {
    const target = kept(s);
    const variants = s.names.map((n) => n.artist).filter((n) => n !== target && included(s, n));
    void apply(() => api.mergeSpellings(target, variants), `Could not merge into ${target}.`);
  }

  function byHand(e: Event) {
    e.preventDefault();
    const target = canonical.trim();
    const from = variant.trim();
    if (!target || !from) return;
    void apply(async () => {
      const result = await api.mergeSpellings(target, [from]);
      variant = '';
      canonical = '';
      return result;
    }, `Could not merge ${from} into ${target}.`);
  }
</script>

{#if status === 'error'}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if status === 'ok' && data}
  <div class="dashboard">
    <section class="glass intro">
      <h1>Spellings</h1>
      <p>
        Last.fm sometimes hands one artist over in several spellings. Merging them counts their
        listens under one name everywhere, including new scrobbles and imports. The original
        spelling stays stored, so every merge can be undone.
      </p>
    </section>

    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <section class="glass" aria-labelledby="suggestions-heading">
      <h2 id="suggestions-heading">Look alike</h2>
      {#if data.suggestions.length === 0}
        <p class="empty">No artists look alike right now.</p>
      {:else}
        <p class="note">Pick the name to keep. Nothing is merged until you say so.</p>
        <div class="suggestions">
          {#each data.suggestions as s (id(s))}
            <fieldset class="suggestion" aria-label={id(s)}>
              <ul>
                {#each s.names as n (n.artist)}
                  <li>
                    <label class="keep">
                      <input
                        type="radio"
                        name={`keep-${id(s)}`}
                        checked={kept(s) === n.artist}
                        onchange={() => (keep[id(s)] = n.artist)}
                      />
                      <span class="name">{n.artist}</span>
                      <span class="count">{listens(n.listens)}</span>
                    </label>
                    {#if kept(s) !== n.artist}
                      <input
                        type="checkbox"
                        aria-label={`Include ${n.artist}`}
                        checked={included(s, n.artist)}
                        onchange={() => toggle(s, n.artist)}
                      />
                    {/if}
                  </li>
                {/each}
              </ul>
              <button
                type="button"
                class="primary"
                disabled={busy || s.names.every((n) => n.artist === kept(s) || !included(s, n.artist))}
                onclick={() => accept(s)}
              >Merge into {kept(s)}</button>
            </fieldset>
          {/each}
        </div>
      {/if}
      <form class="manual" onsubmit={byHand}>
        <span class="heading">Not listed?</span>
        <label>
          <span>Spelling</span>
          <input type="text" bind:value={variant} autocomplete="off" spellcheck="false" maxlength="500" />
        </label>
        <label>
          <span>Merge into</span>
          <input type="text" bind:value={canonical} autocomplete="off" spellcheck="false" maxlength="500" />
        </label>
        <button type="submit" disabled={busy || !variant.trim() || !canonical.trim()}>Merge</button>
      </form>
    </section>

    <section class="glass" aria-labelledby="merges-heading">
      <h2 id="merges-heading">Merged</h2>
      {#if data.merges.length === 0}
        <p class="empty">Nothing merged yet.</p>
      {:else}
        <ul class="merges">
          {#each data.merges as m (m.canonical)}
            <li aria-label={m.canonical}>
              <div class="head">
                <span class="name">{m.canonical}</span>
                <span class="count">{listens(m.listens)}</span>
                <button
                  type="button"
                  class="ghost"
                  disabled={busy}
                  onclick={() => apply(() => api.unmerge(m.canonical), `Could not undo the merge into ${m.canonical}.`)}
                >Undo merge</button>
              </div>
              <ul class="variants">
                {#each m.variants as v (v.artist)}
                  <li>
                    <span class="from">{v.artist}</span>
                    <span class="count">{listens(v.listens)}</span>
                    <button
                      type="button"
                      class="ghost"
                      aria-label={`Split off ${v.artist}`}
                      disabled={busy}
                      onclick={() => apply(() => api.unmerge(m.canonical, v.artist), `Could not split off ${v.artist}.`)}
                    >Split off</button>
                  </li>
                {/each}
              </ul>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
{/if}

<style>
  section {
    padding: 1.4rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  h1 {
    font-size: 1.6rem;
    margin: 0;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
    margin: 0;
  }
  .intro p,
  .note,
  .empty {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
    line-height: 1.5;
    max-width: 46rem;
  }
  .empty {
    color: var(--text-dim);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .suggestions {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 19rem), 1fr));
    gap: 0.8rem;
  }
  .suggestion {
    margin: 0;
    border: 0;
    padding: 0.8rem 0.9rem;
    border-radius: var(--r-sm);
    background: var(--mantle);
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    min-width: 0;
  }
  .suggestion ul {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .suggestion li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .keep {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex: 1;
    min-width: 0;
    cursor: pointer;
  }
  .keep input {
    align-self: center;
  }
  .name {
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .from {
    overflow-wrap: anywhere;
  }
  .count {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-muted);
    white-space: nowrap;
  }
  input[type='radio'],
  input[type='checkbox'] {
    accent-color: var(--accent);
    margin: 0;
  }
  .suggestion button {
    align-self: flex-start;
  }
  .merges {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .merges > li {
    padding: 0.6rem 0.8rem;
    border-radius: var(--r-sm);
    background: var(--mantle);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .head,
  .variants li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .head button {
    margin-left: auto;
  }
  .variants {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding-left: 1rem;
    border-left: 2px solid var(--surface0);
    font-size: 0.88rem;
  }
  .variants button {
    padding: 0.15rem 0.6rem;
    font-size: 0.75rem;
  }
  .manual {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 0.5rem 0.7rem;
    padding-top: 0.4rem;
    border-top: 1px solid var(--surface0);
  }
  .heading {
    width: 100%;
    font-size: 0.82rem;
    color: var(--text-muted);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .keep {
    flex-direction: row;
    font-size: 0.92rem;
    color: var(--text);
  }
  input[type='text'] {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
    width: 14rem;
    max-width: 100%;
  }
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
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
  button:hover:not(:disabled) {
    background: var(--surface1);
  }
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  button:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .primary,
  .primary:hover:not(:disabled) {
    background: var(--accent);
    color: var(--accent-contrast);
  }
  .ghost {
    color: var(--text-muted);
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
</style>
