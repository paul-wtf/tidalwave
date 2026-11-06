<script lang="ts">
  import TrackPage from '$lib/components/TrackPage.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<TrackPage token={data.token} />
