<script lang="ts">
  import { WAVE_HEIGHT, WAVE_WIDTH, wavePaths } from '$lib/wave';

  let { values }: { values: number[] } = $props();

  const paths = $derived(wavePaths(values));
</script>

{#if paths.length}
  <div class="wave" aria-hidden="true">
    <svg class="sky" viewBox="0 0 {WAVE_WIDTH} {WAVE_HEIGHT}" preserveAspectRatio="xMidYMax slice">
      <circle class="halo" cx="1190" cy="300" r="110" />
      <circle class="moon" cx="1190" cy="300" r="72" />
    </svg>
    <svg class="ridges" viewBox="0 0 {WAVE_WIDTH} {WAVE_HEIGHT}" preserveAspectRatio="none">
      {#each paths as d, i (i)}
        <path class="layer l{i}" {d} />
      {/each}
    </svg>
  </div>
{/if}

<style>
  /* Sits on top of the static wallpaper (body::before, same z-index, earlier
     in the tree) and hides it with the opaque canvas colour. */
  .wave {
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: var(--canvas);
    animation: wave-in var(--dur-slow) var(--ease-out) both;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .halo,
  .moon {
    fill: var(--accent);
  }
  .halo {
    opacity: var(--moon-halo);
  }
  .moon {
    opacity: var(--moon-core);
  }
  .layer {
    transition: d var(--dur-slow) var(--ease-out);
  }
  .l0 {
    fill: var(--hill-1);
    opacity: 0.55;
  }
  .l1 {
    fill: var(--hill-2);
    opacity: 0.8;
  }
  .l2 {
    fill: var(--hill-3);
  }
  .l3 {
    fill: var(--hill-4);
  }
  @keyframes wave-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .wave {
      animation: none;
    }
    .layer {
      transition: none;
    }
  }
</style>
