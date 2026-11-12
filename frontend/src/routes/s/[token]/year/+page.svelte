<script lang="ts">
  import YearIndex from '$lib/components/YearIndex.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<YearIndex token={data.token} />
