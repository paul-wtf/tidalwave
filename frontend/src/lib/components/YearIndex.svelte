<script lang="ts">
  import { goto } from '$app/navigation';
  import { statsApi } from '$lib/api/client';

  let { token }: { token?: string } = $props();

  let status = $state<'loading' | 'empty' | 'error'>('loading');

  $effect(() => {
    const base = token ? `/s/${token}` : '';
    statsApi(token)
      .years()
      .then((years) => {
        if (years.length === 0) status = 'empty';
        else void goto(`${base}/year/${years[0].year}`, { replaceState: true });
      })
      .catch(() => (status = 'error'));
  });
</script>

{#if status === 'empty'}
  <p class="msg">{token ? 'This share does not cover a whole year.' : 'No listens yet.'}</p>
{:else if status === 'error'}
  <p class="msg">Could not load this page. Please try again.</p>
{/if}

<style>
  .msg {
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
