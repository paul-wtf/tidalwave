<script lang="ts">
  import { onMount } from 'svelte';
  import { statsApi, type NowPlaying } from '$lib/api/client';
  import { artistHref, trackHref } from '$lib/links';
  import Cover from './Cover.svelte';

  // The backend caches Last.fm's answer for 15 seconds, so asking more often
  // than this would mostly return the same thing.
  const POLL_MS = 30_000;

  let track = $state<NowPlaying | null>(null);
  let live = $state(false);

  onMount(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    let mounted = true;

    async function ask() {
      try {
        const answer = await statsApi().nowPlaying();
        if (!mounted) return;
        track = answer;
        live = answer !== null;
      } catch {
        if (mounted) live = false;
      }
    }
    function stop() {
      clearInterval(timer);
      timer = undefined;
    }
    function start() {
      stop();
      void ask();
      timer = setInterval(ask, POLL_MS);
    }
    function onVisibility() {
      if (document.visibilityState === 'visible') start();
      else stop();
    }

    document.addEventListener('visibilitychange', onVisibility);
    if (document.visibilityState === 'visible') start();
    return () => {
      mounted = false;
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  });
</script>

{#if track}
  <section class="now glass" aria-label="Now playing">
    <Cover src={track.image_url} alt="" size={48} />
    <div class="text">
      <span class="eyebrow">now playing</span>
      <a class="title" href={trackHref('', track.artist, track.track)}>{track.track}</a>
      <a class="artist" href={artistHref('', track.artist)}>{track.artist}</a>
    </div>
    <span class="eq" class:live data-testid="equalizer" aria-hidden="true"><i></i><i></i><i></i></span>
  </section>
{/if}

<style>
  .now {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    padding: 0.8rem 1.4rem 0.8rem 0.8rem;
  }
  .text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    line-height: 1.35;
  }
  a {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-decoration: none;
  }
  a:hover {
    color: var(--accent-text);
  }
  .title {
    color: var(--text);
    font-weight: 700;
  }
  .artist {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .eq {
    display: flex;
    align-items: flex-end;
    gap: 3px;
    height: 20px;
  }
  .eq i {
    width: 4px;
    height: 100%;
    border-radius: 2px;
    background: var(--accent);
    transform-origin: bottom;
  }
  .eq i:nth-child(1) {
    transform: scaleY(0.45);
  }
  .eq i:nth-child(2) {
    transform: scaleY(0.9);
  }
  .eq i:nth-child(3) {
    transform: scaleY(0.65);
  }
  .eq.live i {
    animation: bounce 900ms var(--ease-out) infinite alternate;
  }
  .eq.live i:nth-child(2) {
    animation-duration: 700ms;
    animation-delay: -300ms;
  }
  .eq.live i:nth-child(3) {
    animation-duration: 1100ms;
    animation-delay: -500ms;
  }
  @keyframes bounce {
    from {
      transform: scaleY(0.25);
    }
    to {
      transform: scaleY(1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .eq.live i {
      animation: none;
    }
  }
</style>
