<script lang="ts">
  import { api } from '$lib/api/client';
</script>

<a class="connect" href={api.loginUrl()}>Connect with Last.fm</a>

<style>
  .connect {
    display: inline-block;
    background: var(--accent-text);
    color: var(--accent-contrast);
    font-weight: 700;
    padding: 0.8rem 1.6rem;
    border-radius: var(--r-sm);
    text-decoration: none;
    transition: filter var(--dur-fast) var(--ease-out);
  }
  .connect:hover {
    filter: brightness(1.12);
  }
  .connect:focus-visible {
    outline-offset: 3px;
  }
</style>
