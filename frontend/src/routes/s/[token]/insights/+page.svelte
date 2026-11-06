<script lang="ts">
  import InsightsPage from '$lib/components/InsightsPage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<InsightsPage token={data.token} />
