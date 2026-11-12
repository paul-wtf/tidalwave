<script lang="ts">
  import CompareView from '$lib/components/CompareView.svelte';
  let { data }: { data: { id: number } } = $props();
</script>

{#key data.id}
  <CompareView id={data.id} />
{/key}
