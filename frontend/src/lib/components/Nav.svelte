<script lang="ts">
  import { page } from '$app/stores';

  const DEFAULT_LINKS = [
    { href: '/', label: 'Overview' },
    { href: '/artists', label: 'Artists' },
    { href: '/tracks', label: 'Tracks' },
    { href: '/albums', label: 'Albums' },
    { href: '/insights', label: 'Insights' }
  ];

  let { links = DEFAULT_LINKS, admin = false }:
    { links?: { href: string; label: string }[]; admin?: boolean } = $props();

  const shown = $derived(admin ? [...links, { href: '/admin', label: 'Admin' }] : links);
</script>

<nav aria-label="Sections">
  {#each shown as link (link.href)}
    <a href={link.href} aria-current={$page.url.pathname === link.href ? 'page' : undefined}>
      {link.label}
    </a>
  {/each}
</nav>

<style>
  nav {
    display: flex;
    gap: 0.25rem;
    align-items: center;
  }
  a {
    padding: 0.32rem 0.7rem;
    border-radius: var(--r-xs);
    font-size: 0.85rem;
    color: var(--text-muted);
    text-decoration: none;
    white-space: nowrap;
    transition: color var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out);
  }
  a:hover {
    color: var(--text);
  }
  a[aria-current='page'] {
    color: var(--text);
    background: var(--surface0);
  }
</style>
