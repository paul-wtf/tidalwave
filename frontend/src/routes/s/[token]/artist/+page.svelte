<script lang="ts">
  import ArtistPage from '$lib/components/ArtistPage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<ArtistPage token={data.token} />
