<script lang="ts">
  import '@fontsource-variable/jetbrains-mono';
  import '@fontsource-variable/jetbrains-mono/wght-italic.css';
  import '$lib/theme/tokens.css';
  import { onMount } from 'svelte';
  import { loadConfig } from '$lib/stores/config';
  let { children } = $props();

  onMount(() => {
    void loadConfig();
  });
</script>

{@render children?.()}

<!-- Zen-Frame, as in Frame.qml / paul.wtf: a mantle border strip around the
     viewport with concave corners. The top edge is normally replaced by the
     header (--viewport-top overridden to --bar-h in Header.svelte); routes
     without a header fall back to the plain --frame thickness. -->
<div class="zen-frame" aria-hidden="true"><i></i><i></i><i></i><i></i></div>

<style>
  .zen-frame {
    position: fixed;
    inset: 0;
    border: solid var(--mantle);
    border-width: var(--viewport-top) var(--frame) var(--frame);
    pointer-events: none;
    z-index: 60;
  }
  .zen-frame i {
    position: absolute;
    width: var(--viewport-r);
    height: var(--viewport-r);
  }
  .zen-frame i:nth-child(1) {
    top: 0;
    left: 0;
    background: radial-gradient(circle at 100% 100%, transparent calc(var(--viewport-r) - 0.5px), var(--mantle) var(--viewport-r));
  }
  .zen-frame i:nth-child(2) {
    top: 0;
    right: 0;
    background: radial-gradient(circle at 0% 100%, transparent calc(var(--viewport-r) - 0.5px), var(--mantle) var(--viewport-r));
  }
  .zen-frame i:nth-child(3) {
    bottom: 0;
    left: 0;
    background: radial-gradient(circle at 100% 0%, transparent calc(var(--viewport-r) - 0.5px), var(--mantle) var(--viewport-r));
  }
  .zen-frame i:nth-child(4) {
    bottom: 0;
    right: 0;
    background: radial-gradient(circle at 0% 0%, transparent calc(var(--viewport-r) - 0.5px), var(--mantle) var(--viewport-r));
  }
</style>
