<script lang="ts">
  import { api, type ComparePair, type CompareInvite } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatLongDate } from '$lib/format';

  let pairs = $state<ComparePair[]>([]);
  let invites = $state<CompareInvite[]>([]);
  let loaded = $state(false);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let ending = $state<number | null>(null);
  let copied = $state<string | null>(null);

  const tz = $derived($auth.user?.timezone ?? 'UTC');
  const link = (token: string) => `${location.origin}/compare/invite/${token}`;

  $effect(() => {
    api.comparisons().then(
      (o) => {
        pairs = o.pairs;
        invites = o.invites;
        loaded = true;
      },
      () => (error = 'Could not load your comparisons.')
    );
  });

  async function create() {
    busy = true;
    error = null;
    try {
      invites = [await api.createInvite(), ...invites];
    } catch {
      error = 'Could not create an invite link.';
    } finally {
      busy = false;
    }
  }

  async function revoke(token: string) {
    error = null;
    try {
      await api.revokeInvite(token);
      invites = invites.filter((i) => i.token !== token);
    } catch {
      error = 'Could not revoke the invite link.';
    }
  }

  async function copy(token: string) {
    try {
      await navigator.clipboard.writeText(link(token));
      copied = token;
    } catch {
      error = 'Could not copy the link.';
    }
  }

  async function end(pair: ComparePair) {
    error = null;
    try {
      await api.endComparison(pair.id);
      pairs = pairs.filter((p) => p.id !== pair.id);
      ending = null;
    } catch {
      error = `Could not end the comparison with ${pair.partner}.`;
    }
  }
</script>

<div class="dashboard">
  <section class="glass intro">
    <h1>Compare</h1>
    <p>
      See how your listening overlaps with someone else's. Send them an invite link; once they
      accept, both of you see each other's top artists for any range either of you picks.
      Either of you can end it at any time. Nothing is shared before they accept.
    </p>
    <div>
      <button type="button" class="primary" onclick={create} disabled={busy}>Create invite link</button>
    </div>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
  </section>

  {#if invites.length > 0}
    <section class="glass" aria-labelledby="invites-heading">
      <h2 id="invites-heading">Open invites</h2>
      <p class="note">Each link works once. Revoke one you no longer want to be used.</p>
      <ul>
        {#each invites as invite (invite.token)}
          <li aria-label="Invite link">
            <div class="info">
              <span class="link">{link(invite.token)}</span>
              <span class="meta">created {formatLongDate(invite.created_at, tz)}</span>
            </div>
            <button type="button" onclick={() => copy(invite.token)}>
              {copied === invite.token ? 'Copied' : 'Copy'}
            </button>
            <button type="button" class="ghost" onclick={() => revoke(invite.token)}>Revoke</button>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if loaded}
    <section class="glass" aria-labelledby="pairs-heading">
      <h2 id="pairs-heading">Comparing with</h2>
      {#if pairs.length === 0}
        <p class="empty">Nobody yet. Send someone an invite link.</p>
      {:else}
        <ul>
          {#each pairs as pair (pair.id)}
            <li aria-label={pair.partner ?? 'Comparison'}>
              <div class="info">
                <a class="name" href={`/compare/${pair.id}`}>{pair.partner}</a>
                <span class="meta">since {formatLongDate(pair.created_at, tz)}</span>
              </div>
              {#if ending === pair.id}
                <div class="confirm">
                  <span>You and {pair.partner} stop seeing each other's listening.</span>
                  <button type="button" onclick={() => (ending = null)}>Cancel</button>
                  <button type="button" class="destroy" onclick={() => end(pair)}>End comparison</button>
                </div>
              {:else}
                <button type="button" class="ghost" onclick={() => (ending = pair.id)}>End</button>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}
</div>

<style>
  section {
    padding: 1.4rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }
  h1 {
    font-size: 1.8rem;
  }
  h2 {
    font-size: 1.35rem;
    color: var(--text);
  }
  .intro p {
    margin: 0;
    max-width: 62ch;
    color: var(--text-muted);
  }
  .note,
  .empty {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
  }
  .empty {
    color: var(--text-dim);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.6rem;
    padding: 0.55rem 0.7rem;
    border-radius: var(--r-xs);
  }
  li:nth-child(odd) {
    background: var(--mantle);
  }
  .info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .name {
    font-weight: 600;
    color: var(--text);
    text-decoration: none;
  }
  .name:hover {
    color: var(--accent-text);
  }
  .link {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-dim);
  }
  .confirm {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.6rem;
    padding: 0.5rem 0.7rem;
    border-radius: var(--r-sm);
    background: var(--error-soft);
    font-size: 0.82rem;
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
  .destroy,
  .destroy:hover:not(:disabled) {
    background: var(--error);
    color: var(--accent-contrast);
  }
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.85rem;
  }
</style>
