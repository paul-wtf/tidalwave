<script lang="ts">
  import { api, ApiError, type ImportJob } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatCount, formatLongDate, formatLongDateTime } from '$lib/format';

  let { pollMs = 1500 }: { pollMs?: number } = $props();

  let jobs = $state<ImportJob[]>([]);
  let status = $state<'loading' | 'ok' | 'error'>('loading');
  let file = $state<File | null>(null);
  let uploading = $state(false);
  let error = $state<string | null>(null);
  let confirming = $state<number | null>(null);
  let input = $state<HTMLInputElement>();

  const tz = $derived($auth.user?.timezone ?? 'UTC');
  const active = $derived(jobs.find((j) => j.status === 'pending' || j.status === 'running'));
  const SOURCES: Record<string, string> = { spotify: 'Spotify', listenbrainz: 'ListenBrainz' };
  const STATUS: Record<ImportJob['status'], string> = {
    pending: 'Waiting…', running: 'Importing…', done: 'Done', failed: 'Failed', undone: 'Undone'
  };
  const n = formatCount;

  async function load() {
    try {
      jobs = await api.imports();
      status = 'ok';
    } catch {
      status = 'error';
    }
  }

  $effect(() => {
    void load();
  });

  $effect(() => {
    const id = active?.id;
    if (id == null) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const fresh = await api.importJob(id);
        if (stopped) return;
        jobs = jobs.map((j) => (j.id === id ? fresh : j));
        if (fresh.status === 'pending' || fresh.status === 'running') timer = setTimeout(tick, pollMs);
      } catch {
        if (!stopped) timer = setTimeout(tick, pollMs * 4);
      }
    };
    timer = setTimeout(tick, pollMs);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  });

  function pick(e: Event) {
    file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null;
    error = null;
  }

  async function upload(e: Event) {
    e.preventDefault();
    if (!file) return;
    uploading = true;
    error = null;
    try {
      const job = await api.uploadImport(file, file.name);
      jobs = [job, ...jobs];
      file = null;
      if (input) input.value = '';
    } catch (err) {
      const code = err instanceof ApiError ? err.status : 0;
      error =
        code === 413 ? 'This file is too large to import. Upload the history files one by one.'
        : code === 409 ? 'Another import is already running. Wait for it to finish.'
        : code === 422 ? 'This file is empty.'
        : 'Could not upload the file. Please try again.';
    } finally {
      uploading = false;
    }
  }

  async function undo(job: ImportJob) {
    error = null;
    try {
      const undone = await api.undoImport(job.id);
      jobs = jobs.map((j) => (j.id === job.id ? undone : j));
      confirming = null;
    } catch {
      error = `Could not undo the import of ${job.filename}.`;
    }
  }

  const span = (job: ImportJob) =>
    job.first_played_at && job.last_played_at
      ? `${formatLongDate(job.first_played_at, tz)} to ${formatLongDate(job.last_played_at, tz)}`
      : null;
</script>

{#if status === 'error'}
  <p class="msg">Could not load this page. Please try again.</p>
{:else if status === 'ok'}
  <div class="dashboard">
    <section class="glass intro">
      <h1>Import older history</h1>
      <p>
        Bring in what you listened to before Last.fm scrobbled it. Plays that Last.fm already has
        are recognised and left out, and only plays Last.fm would have counted are added: at least
        30 seconds, and half the track or four minutes when its length is known. Merged spellings
        apply to imported plays too.
      </p>
      <ul class="formats">
        <li>
          <strong>Spotify</strong>: the <em>Extended streaming history</em> from your account's
          privacy settings. Upload the zip, or the <code>Streaming_History_Audio_*.json</code>
          files one by one. Podcasts and private sessions are skipped.
        </li>
        <li>
          <strong>ListenBrainz</strong>: the export from your ListenBrainz settings, as the zip or
          a single listens file.
        </li>
      </ul>
      <form class="upload" onsubmit={upload}>
        <label>
          <span>History file</span>
          <input
            bind:this={input}
            type="file"
            accept=".json,.jsonl,.zip,application/json,application/zip"
            onchange={pick}
          />
        </label>
        <button type="submit" class="primary" disabled={!file || uploading || active != null}>
          {uploading ? 'Uploading…' : 'Import'}
        </button>
      </form>
      {#if error}<p class="error" role="alert">{error}</p>{/if}
    </section>

    <section class="glass" aria-labelledby="imports-heading">
      <h2 id="imports-heading">Imports</h2>
      {#if jobs.length === 0}
        <p class="empty">No imports yet.</p>
      {:else}
        <ul class="jobs">
          {#each jobs as job (job.id)}
            <li aria-label={job.filename} class:running={job.status === 'pending' || job.status === 'running'}>
              <div class="head">
                <span class="name">{job.filename}</span>
                {#if job.source}<span class="tag">{SOURCES[job.source] ?? job.source}</span>{/if}
                <span class="state" class:failed={job.status === 'failed'}>{STATUS[job.status]}</span>
                {#if (job.status === 'done' || job.status === 'failed') && job.added > 0 && confirming !== job.id}
                  <button type="button" class="ghost" onclick={() => (confirming = job.id)}>Undo</button>
                {/if}
              </div>
              <div class="counts">
                <span class="added">
                  {n(job.added)} {job.status === 'undone' ? 'added, then removed' : 'added'}
                </span>
                <span>{n(job.duplicates)} already there</span>
                <span>{n(job.too_short)} too short</span>
                <span>{n(job.skipped)} skipped</span>
                <span>{n(job.read)} read</span>
              </div>
              {#if job.status === 'pending' || job.status === 'running'}
                <div class="bar" aria-hidden="true"><i></i></div>
              {/if}
              <div class="facts">
                {#if span(job)}<span>{span(job)}</span>{/if}
                <span>Uploaded {formatLongDateTime(job.created_at, tz)}</span>
              </div>
              {#if job.error}<p class="reason">{job.error}</p>{/if}
              {#if confirming === job.id}
                <div class="danger">
                  <p>
                    This removes the {n(job.added)} listens this import added. Listens from Last.fm
                    and from other imports stay. You can import the file again later.
                  </p>
                  <div class="row">
                    <button type="button" onclick={() => (confirming = null)}>Cancel</button>
                    <button type="button" class="destroy" onclick={() => undo(job)}>
                      Remove {n(job.added)} listens
                    </button>
                  </div>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
{/if}

<style>
  section {
    padding: 1.4rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  h1 {
    font-size: 1.6rem;
    margin: 0;
  }
  h2 {
    font-size: 1.35rem;
    margin: 0;
  }
  .intro p,
  .formats {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
    line-height: 1.55;
    max-width: 48rem;
  }
  .formats {
    padding-left: 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .formats strong {
    color: var(--text);
  }
  code {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    overflow-wrap: anywhere;
  }
  .upload {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 0.6rem 0.8rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: var(--text-muted);
    min-width: 0;
    max-width: 100%;
  }
  input[type='file'] {
    font-size: 0.82rem;
    color: var(--text);
    max-width: 100%;
  }
  input[type='file']::file-selector-button {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    margin-right: 0.7rem;
    cursor: pointer;
    font: inherit;
  }
  .empty {
    margin: 0;
    color: var(--text-dim);
    font-size: 0.88rem;
  }
  ul.jobs {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .jobs > li {
    padding: 0.7rem 0.85rem;
    border-radius: var(--r-sm);
    background: var(--mantle);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .name {
    font-weight: 600;
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .tag {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    padding: 0.05rem 0.45rem;
    border-radius: var(--r-xs);
    background: var(--accent-soft);
  }
  .state {
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .state.failed,
  .reason {
    color: var(--error);
  }
  .head button {
    margin-left: auto;
  }
  .counts,
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 1.1rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .counts .added {
    color: var(--text);
    font-weight: 600;
  }
  .facts {
    color: var(--text-dim);
    font-size: 0.7rem;
  }
  .reason {
    margin: 0;
    font-size: 0.8rem;
  }
  .bar {
    height: 3px;
    border-radius: 2px;
    background: var(--surface0);
    overflow: hidden;
  }
  .bar i {
    display: block;
    height: 100%;
    width: 35%;
    border-radius: 2px;
    background: var(--accent);
    animation: slide 1.4s var(--ease-out) infinite;
  }
  @keyframes slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(300%);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .bar i {
      animation: none;
      width: 100%;
      opacity: 0.5;
    }
  }
  .danger {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.8rem;
    border-radius: var(--r-sm);
    background: var(--error-soft);
  }
  .danger p {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  button {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.4rem 0.85rem;
    font-size: 0.82rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  button:hover:not(:disabled) {
    background: var(--surface1);
  }
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  button:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .primary,
  .primary:hover:not(:disabled) {
    background: var(--accent);
    color: var(--accent-contrast);
  }
  .destroy,
  .destroy:hover:not(:disabled) {
    background: var(--error);
    color: var(--accent-contrast);
  }
  .ghost {
    color: var(--text-muted);
  }
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.85rem;
  }
  .msg {
    max-width: 1180px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
</style>
