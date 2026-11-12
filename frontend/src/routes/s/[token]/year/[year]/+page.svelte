<script lang="ts">
  import YearReview from '$lib/components/YearReview.svelte';
  let { data }: { data: { token: string; year: number } } = $props();
</script>

{#key data.year}<YearReview year={data.year} token={data.token} />{/key}
