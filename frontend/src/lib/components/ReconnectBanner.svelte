<script lang="ts">
  import { auth } from '$lib/stores/auth';
</script>

{#if $auth.user?.disconnected}
  <div class="banner" role="alert">
    <span>Last.fm access was revoked. Reconnect to keep tracking.</span>
    <a href="/auth/login">Reconnect</a>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding: 0.6rem 1.5rem;
    background: var(--surface0);
    color: var(--text);
    font-size: 0.88rem;
  }
  a {
    color: var(--accent-text);
    font-weight: 600;
  }
</style>
