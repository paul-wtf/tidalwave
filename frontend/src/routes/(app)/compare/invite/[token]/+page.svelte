<script lang="ts">
  import InviteAccept from '$lib/components/InviteAccept.svelte';
  let { data }: { data: { token: string } } = $props();
</script>

<InviteAccept token={data.token} />
