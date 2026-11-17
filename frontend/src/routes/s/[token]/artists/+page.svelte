<script lang="ts">
  import TopPage from '#lib/components/TopPage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<TopPage kind="artists" token={data.token} errorMessage="This shared link was not found or has been revoked." />
