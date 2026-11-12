<script lang="ts">
  import { page } from '$app/stores';

  const DEFAULT_LINKS = [
    { href: '/', label: 'Overview' },
    { href: '/artists', label: 'Artists' },
    { href: '/tracks', label: 'Tracks' },
    { href: '/albums', label: 'Albums' },
    { href: '/insights', label: 'Insights' },
    { href: '/year', label: 'Year', section: true },
    { href: '/compare', label: 'Compare', section: true }
  ];

  type Link = { href: string; label: string; section?: boolean };
  let { links = DEFAULT_LINKS, admin = false }: { links?: Link[]; admin?: boolean } = $props();

  const current = (link: Link, path: string) =>
    path === link.href || (link.section === true && path.startsWith(`${link.href}/`));

  const shown = $derived(admin ? [...links, { href: '/admin', label: 'Admin' }] : links);
  const here = $derived(shown.find((link) => current(link, $page.url.pathname)));

  const uid = $props.id();
  const listId = `${uid}-sections`;
  let open = $state(false);
  let root: HTMLElement | undefined = $state();
  let toggle: HTMLButtonElement | undefined = $state();

  function onWindowClick(e: MouseEvent) {
    if (open && root && !e.composedPath().includes(root)) open = false;
  }

  function onWindowKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') {
      open = false;
      toggle?.focus();
    }
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<nav aria-label="Sections" bind:this={root}>
  <button
    type="button"
    class="toggle"
    aria-expanded={open}
    aria-controls={listId}
    bind:this={toggle}
    onclick={() => (open = !open)}
  >
    <span class="sr-only">Sections:</span>
    {here?.label ?? 'Sections'}
    <span class="chevron" aria-hidden="true"></span>
  </button>
  <div class="links" class:open id={listId}>
    {#each shown as link (link.href)}
      <a
        href={link.href}
        aria-current={current(link, $page.url.pathname) ? 'page' : undefined}
        onclick={() => (open = false)}
      >
        {link.label}
      </a>
    {/each}
  </div>
</nav>

<style>
  nav,
  .links {
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
  a:focus-visible,
  .toggle:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  .toggle {
    display: none;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  /* Seven or eight entries do not fit next to the brand on a phone, so
     they fold into one menu there; the header keeps its two fixed rows. */
  @media (max-width: 640px) {
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      background: var(--surface0);
      color: var(--text);
      border: 0;
      border-radius: var(--r-sm);
      padding: 0.4rem 0.75rem;
      font-size: 0.85rem;
      cursor: pointer;
    }
    .chevron {
      width: 0.4rem;
      height: 0.4rem;
      border-right: 1.5px solid currentColor;
      border-bottom: 1.5px solid currentColor;
      transform: translateY(-2px) rotate(45deg);
      transition: transform var(--dur-fast) var(--ease-out);
    }
    .toggle[aria-expanded='true'] .chevron {
      transform: translateY(1px) rotate(-135deg);
    }
    .links {
      display: none;
    }
    .links.open {
      position: fixed;
      top: var(--bar-h);
      left: clamp(1rem, 4vw, 1.5rem);
      right: clamp(1rem, 4vw, 1.5rem);
      z-index: 10;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.3rem;
      padding: 0.6rem;
      background: var(--surface0);
      border-radius: var(--r-sm);
      box-shadow: 0 4px 16px rgb(0 0 0 / 0.25);
    }
    .links a {
      padding: 0.6rem 0.75rem;
      font-size: 0.9rem;
    }
    .links a[aria-current='page'] {
      background: var(--surface1);
    }
  }
</style>
