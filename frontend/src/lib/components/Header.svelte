<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
  import type { Snippet } from 'svelte';
  let { nav, children }: { nav?: Snippet; children?: Snippet } = $props();
</script>

<header class="zen-bar">
  <div class="lead">
    <a class="brand" href="/">
      <span class="mark" aria-hidden="true"></span>
      tidalwave
    </a>
    {@render nav?.()}
  </div>
  <div class="actions">
    {@render children?.()}
    <ThemeToggle />
  </div>
</header>

<style>
  /* This bar IS the top edge of the zen-frame (see routes/+layout.svelte) —
     --viewport-top must track its real rendered height exactly, or the
     frame's top border and its concave corners drift off the bar. Bound to
     the bar actually being in the DOM (:has), not to this stylesheet being
     loaded — component CSS stays loaded across client-side navigation, so a
     plain :root rule would leave a barless 60px mantle band on headerless
     routes (default error page) after SPA nav. */
  :global(:root:has(.zen-bar)) {
    --viewport-top: var(--bar-h);
  }

  header {
    position: sticky;
    top: 0;
    /* Above the zen-frame (z-index 60): its opaque top border is --bar-h
       tall and would paint over the bar — like Nav.astro (70) on paul.wtf. */
    z-index: 70;
    height: var(--bar-h);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.25rem;
    padding: 0 clamp(1rem, 4vw, 2rem);
    background: var(--mantle);
    overflow: hidden;
  }
  .lead {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    height: 100%;
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.35rem;
    line-height: 1;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
  }
  /* Tide mark: a small solid square in the accent, echoing the favicon monogram. */
  .mark {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
    background: var(--accent);
  }
  .actions {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    height: 100%;
    flex-shrink: 0;
  }

  /* Below 640px the bar switches to a fixed two-row layout instead of
     wrapping/overflowing organically — --bar-h in tokens.css has a matching
     media-query override so the frame border stays lined up with the real
     header height. Each row scrolls horizontally on overflow rather than
     wrapping further, so the total height stays deterministic. */
  @media (max-width: 640px) {
    header {
      flex-direction: column;
      align-items: stretch;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.5rem clamp(1rem, 4vw, 1.5rem);
    }
    .lead {
      flex: 1 1 0;
      min-height: 0;
      justify-content: space-between;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .lead::-webkit-scrollbar {
      display: none;
    }
    .brand {
      flex-shrink: 0;
    }
    .lead :global(nav) {
      flex-shrink: 0;
    }
    .actions :global(*) {
      flex-shrink: 0;
    }
    .actions {
      flex: 1 1 0;
      min-height: 0;
      justify-content: flex-end;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .actions::-webkit-scrollbar {
      display: none;
    }
  }
</style>
