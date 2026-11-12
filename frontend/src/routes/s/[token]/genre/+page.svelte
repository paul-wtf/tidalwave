<script lang="ts">
  import GenrePage from '$lib/components/GenrePage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<GenrePage token={data.token} />
