<script lang="ts">
  import YearReview from '$lib/components/YearReview.svelte';
  let { data }: { data: { year: number } } = $props();
</script>

{#key data.year}<YearReview year={data.year} />{/key}
