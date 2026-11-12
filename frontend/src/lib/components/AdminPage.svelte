<script lang="ts">
  import { api, ApiError, type AdminUser, type Allowlist } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatCount, formatLongDate, formatRelative } from '$lib/format';

  let users = $state<AdminUser[]>([]);
  let allowlist = $state<Allowlist | null>(null);
  let status = $state<'loading' | 'ok' | 'forbidden' | 'error'>('loading');
  let error = $state<string | null>(null);
  let deleting = $state<number | null>(null);
  let typed = $state('');
  let busy = $state(false);
  let name = $state('');

  const me = $derived($auth.user?.username);
  const tz = $derived($auth.user?.timezone ?? 'UTC');
  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;

  async function load() {
    try {
      [users, allowlist] = await Promise.all([api.adminUsers(), api.allowlist()]);
      status = 'ok';
    } catch (e) {
      status = e instanceof ApiError && e.status === 403 ? 'forbidden' : 'error';
    }
  }

  $effect(() => {
    void load();
  });

  function startDeletion(user: AdminUser) {
    deleting = user.id;
    typed = '';
    error = null;
  }

  async function remove(e: Event, user: AdminUser) {
    e.preventDefault();
    if (typed !== user.username) return;
    busy = true;
    error = null;
    try {
      await api.deleteUser(user.id);
      users = users.filter((u) => u.id !== user.id);
      deleting = null;
    } catch {
      error = `Could not delete ${user.username}.`;
    } finally {
      busy = false;
    }
  }

  async function add(e: Event) {
    e.preventDefault();
    const username = name.trim();
    if (!username || !allowlist) return;
    busy = true;
    error = null;
    try {
      const entry = await api.addToAllowlist(username);
      allowlist.entries = [...allowlist.entries, entry].sort((a, b) =>
        a.username.toLowerCase().localeCompare(b.username.toLowerCase())
      );
      name = '';
    } catch (err) {
      const code = err instanceof ApiError ? err.status : 0;
      error =
        code === 409 ? `${username} is already on the allowlist.`
        : code === 422 ? `${username} is not a Last.fm username.`
        : `Could not add ${username}.`;
    } finally {
      busy = false;
    }
  }

  async function unlist(username: string) {
    if (!allowlist) return;
    error = null;
    try {
      await api.removeFromAllowlist(username);
      allowlist.entries = allowlist.entries.filter((e) => e.username !== username);
    } catch {
      error = `Could not remove ${username}.`;
    }
  }
</script>

{#if status === 'forbidden'}
  <p class="msg">Only admins can see this page.</p>
{:else if status === 'error'}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if status === 'ok' && allowlist}
  <div class="dashboard">
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <section class="glass" aria-labelledby="users-heading">
      <h2 id="users-heading">Users</h2>
      <ul class="users">
        {#each users as user (user.id)}
          <li aria-label={user.username}>
            <div class="who">
              <span class="name">{user.username}</span>
              {#if user.is_admin}<span class="tag">admin</span>{/if}
              {#if user.disconnected}<span class="tag warn">disconnected</span>{/if}
            </div>
            <div class="facts">
              <span>{listens(user.listens)}</span>
              <span>Joined {formatLongDate(user.created_at, tz)}</span>
              <span>
                {user.last_synced_at
                  ? `Polled ${formatRelative(user.last_synced_at, new Date())}`
                  : 'Never polled'}
              </span>
            </div>
            {#if user.username !== me && deleting !== user.id}
              <button type="button" class="ghost" onclick={() => startDeletion(user)}>Delete</button>
            {/if}
            {#if deleting === user.id}
              <form class="danger" onsubmit={(e) => remove(e, user)}>
                <p>
                  This deletes {user.username} with {listens(user.listens)}, their share links,
                  comparisons and sync state. It cannot be undone. Their Last.fm account stays as
                  it is, and they can sign up again while the allowlist lets them.
                </p>
                <label>
                  <span>Type {user.username} to confirm</span>
                  <input type="text" bind:value={typed} autocomplete="off" spellcheck="false" />
                </label>
                <div class="row">
                  <button type="button" onclick={() => (deleting = null)}>Cancel</button>
                  <button type="submit" class="destroy" disabled={busy || typed !== user.username}>
                    Delete {user.username} for good
                  </button>
                </div>
              </form>
            {/if}
          </li>
        {/each}
      </ul>
    </section>

    <section class="glass" aria-labelledby="allowlist-heading">
      <h2 id="allowlist-heading">Allowlist</h2>
      {#if allowlist.mode === 'open'}
        <p class="note">
          Registration is open: anyone with a Last.fm account can sign up. The allowlist only
          applies with <code>TIDALWAVE_REGISTRATION_MODE=allowlist</code>.
        </p>
      {:else}
        <p class="note">
          Only these Last.fm users can sign up. Removing a name keeps an existing account.
        </p>
      {/if}
      {#if allowlist.entries.length === 0}
        <p class="empty">Nobody is on the allowlist yet.</p>
      {:else}
        <ul class="entries">
          {#each allowlist.entries as entry (entry.username)}
            <li aria-label={entry.username}>
              <span class="name">{entry.username}</span>
              {#if entry.fixed}
                <span class="source">from TIDALWAVE_REGISTRATION_ALLOWLIST</span>
              {:else}
                {#if entry.added_at}
                  <span class="source">added {formatLongDate(entry.added_at, tz)}</span>
                {/if}
                <button type="button" class="ghost" onclick={() => unlist(entry.username)}>Remove</button>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      <form class="add" onsubmit={add}>
        <label>
          <span>Last.fm username</span>
          <input type="text" bind:value={name} autocomplete="off" spellcheck="false" maxlength="64" />
        </label>
        <button type="submit" disabled={busy || !name.trim()}>Add</button>
      </form>
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
  h2 {
    font-size: 1.35rem;
    color: var(--text);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li {
    display: grid;
    grid-template-columns: 14rem minmax(0, 1fr) auto;
    grid-template-areas: 'who facts action';
    align-items: center;
    gap: 0.4rem 0.9rem;
    padding: 0.55rem 0.7rem;
    border-radius: var(--r-xs);
  }
  li:nth-child(odd) {
    background: var(--mantle);
  }
  li > button {
    grid-area: action;
  }
  .who {
    grid-area: who;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }
  .name {
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .entries .name {
    grid-area: who;
  }
  .tag {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    padding: 0.05rem 0.45rem;
    border-radius: var(--r-xs);
    background: var(--accent-soft);
    color: var(--text);
  }
  .tag.warn {
    background: var(--error-soft);
  }
  .facts {
    grid-area: facts;
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 1.1rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .facts span {
    white-space: nowrap;
  }
  .source {
    grid-area: facts;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-dim);
    overflow-wrap: anywhere;
  }
  @media (max-width: 640px) {
    li {
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas: 'who action' 'facts facts';
    }
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
  code {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    overflow-wrap: anywhere;
  }
  .danger {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.8rem;
    border-radius: var(--r-sm);
    background: var(--error-soft);
  }
  .danger p {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.5;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .danger label {
    color: var(--text);
  }
  input {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
    max-width: 18rem;
  }
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .row,
  .add {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: flex-end;
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
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
