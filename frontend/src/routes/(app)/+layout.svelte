<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { auth, loadMe } from '$lib/stores/auth';
  import { afterLogin } from '$lib/afterLogin';
  import Header from '$lib/components/Header.svelte';
  import Nav from '$lib/components/Nav.svelte';
  import Search from '$lib/components/Search.svelte';
  import RangeSelector from '$lib/components/RangeSelector.svelte';
  import ShareManager from '$lib/components/ShareManager.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import ReconnectBanner from '$lib/components/ReconnectBanner.svelte';
  import Landing from '$lib/components/Landing.svelte';
  import type { Snippet } from 'svelte';

  let { children }: { children?: Snippet } = $props();

  onMount(loadMe);

  const invited = $derived($page.url.pathname.startsWith('/compare/invite/'));

  $effect(() => {
    if ($auth.loading) return;
    const next = afterLogin($page.url.pathname, $auth.user != null, () => sessionStorage);
    if (next) void goto(next);
  });
</script>

<Header>
  {#snippet nav()}
    {#if $auth.user}<Nav admin={$auth.user.is_admin} />{/if}
  {/snippet}
  {#if $auth.user}
    <Search />
    <RangeSelector />
    <ShareManager />
    <UserMenu />
  {/if}
</Header>

{#if $auth.loading}
  <p class="centered">Loading…</p>
{:else if $auth.user}
  <ReconnectBanner />
  {@render children?.()}
{:else}
  {#if invited}
    <p class="invited">
      Someone invited you to compare your listening. Connect your Last.fm account, and the invite
      opens right after.
    </p>
  {/if}
  <Landing />
{/if}

<style>
  .invited {
    max-width: 40rem;
    margin: calc(var(--viewport-r) + 16px) auto 0;
    padding: 0.8rem 1.1rem;
    border-radius: var(--r-sm);
    background: var(--accent-soft);
    text-align: center;
  }
  .centered {
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
