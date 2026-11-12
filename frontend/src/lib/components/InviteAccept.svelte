<script lang="ts">
  import { goto } from '$app/navigation';
  import { api, ApiError, type InviteInfo } from '$lib/api/client';

  let { token }: { token: string } = $props();

  let invite = $state<InviteInfo | null>(null);
  let status = $state<'loading' | 'ok' | 'gone' | 'error'>('loading');
  let busy = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    api.invite(token).then(
      (i) => {
        invite = i;
        status = 'ok';
      },
      (e) => (status = e instanceof ApiError && e.status === 404 ? 'gone' : 'error')
    );
  });

  async function accept() {
    if (!invite) return;
    busy = true;
    error = null;
    try {
      const pair = await api.acceptInvite(token);
      await goto(`/compare/${pair.id}`);
    } catch (e) {
      const code = e instanceof ApiError ? e.status : 0;
      error =
        code === 409 ? `You already compare with ${invite.inviter}.`
        : code === 404 ? 'This invite link is no longer valid.'
        : 'Could not accept the invite.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="dashboard">
  <section class="glass">
    {#if status === 'gone'}
      <h1>Invite not found</h1>
      <p>This invite link is no longer valid. It may have been used or revoked; ask for a new one.</p>
      <p><a href="/compare">Your comparisons</a></p>
    {:else if status === 'error'}
      <p>Could not load this invite. Please try again.</p>
    {:else if invite?.own}
      <h1>Your invite</h1>
      <p>
        This is your own invite link. Send it to the person you want to compare your listening
        with.
      </p>
      <p><a href="/compare">Your comparisons</a></p>
    {:else if invite}
      <h1>{invite.inviter} wants to compare listening with you</h1>
      <p>
        If you accept, you and {invite.inviter} see each other's top artists and how much your
        listening overlaps, for any range either of you picks. Nothing else is shared, and either
        of you can end it at any time.
      </p>
      <div class="row">
        <button type="button" class="primary" onclick={accept} disabled={busy}>Accept</button>
        <a class="button" href="/">Not now</a>
      </div>
      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}
    {/if}
  </section>
</div>

<style>
  section {
    align-self: center;
    width: 100%;
    max-width: 40rem;
    padding: 1.6rem 1.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  h1 {
    font-size: 1.6rem;
  }
  p {
    margin: 0;
    color: var(--text-muted);
  }
  a {
    color: var(--accent-text);
  }
  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  button,
  .button {
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.5rem 1.1rem;
    font-size: 0.88rem;
    cursor: pointer;
    background: var(--surface0);
    color: var(--text);
    text-decoration: none;
  }
  .button:hover {
    background: var(--surface1);
  }
  .primary {
    background: var(--accent);
    color: var(--accent-contrast);
  }
  button:disabled {
    opacity: 0.55;
    cursor: default;
  }
  button:focus-visible,
  .button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .error {
    color: var(--error);
    font-size: 0.85rem;
  }
</style>
