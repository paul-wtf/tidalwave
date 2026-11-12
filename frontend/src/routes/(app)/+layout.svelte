<script lang="ts">
  import { onMount } from 'svelte';
  import { auth, loadMe } from '$lib/stores/auth';
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
  <Landing />
{/if}

<style>
  .centered {
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
