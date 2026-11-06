<script lang="ts">
  import type { Snippet } from 'svelte';
  import Header from '$lib/components/Header.svelte';
  import Nav from '$lib/components/Nav.svelte';

  let { data, children }: { data: { token: string }; children?: Snippet } = $props();

  const links = $derived([
    { href: `/s/${data.token}`, label: 'Overview' },
    { href: `/s/${data.token}/artists`, label: 'Artists' },
    { href: `/s/${data.token}/tracks`, label: 'Tracks' },
    { href: `/s/${data.token}/albums`, label: 'Albums' },
    { href: `/s/${data.token}/insights`, label: 'Insights' }
  ]);
</script>

<Header>
  {#snippet nav()}<Nav {links} />{/snippet}
</Header>

{@render children?.()}
