<script lang="ts">
  import type { Snippet } from 'svelte';
  import { statsApi } from '$lib/api/client';
  import Header from '$lib/components/Header.svelte';
  import Nav from '$lib/components/Nav.svelte';
  import Search from '$lib/components/Search.svelte';

  let { data, children }: { data: { token: string }; children?: Snippet } = $props();

  let latestYear = $state<number | null>(null);

  $effect(() => {
    latestYear = null;
    statsApi(data.token)
      .years()
      .then((years) => (latestYear = years[0]?.year ?? null))
      .catch(() => (latestYear = null));
  });

  const links = $derived([
    { href: `/s/${data.token}`, label: 'Overview' },
    { href: `/s/${data.token}/artists`, label: 'Artists' },
    { href: `/s/${data.token}/tracks`, label: 'Tracks' },
    { href: `/s/${data.token}/albums`, label: 'Albums' },
    { href: `/s/${data.token}/insights`, label: 'Insights' },
    ...(latestYear != null
      ? [{ href: `/s/${data.token}/year/${latestYear}`, label: String(latestYear), section: true }]
      : [])
  ]);
</script>

<Header>
  {#snippet nav()}<Nav {links} />{/snippet}
  <Search token={data.token} />
</Header>

{@render children?.()}
