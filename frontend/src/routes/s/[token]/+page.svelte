<script lang="ts">
  import Dashboard from '#lib/components/Dashboard.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<Dashboard token={data.token} errorMessage="This shared link was not found or has been revoked." />
