<script lang="ts">
  import AlbumPage from '$lib/components/AlbumPage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<AlbumPage token={data.token} />
