<script lang="ts">
  import { api, statsApi, ApiError, type YearCount, type YearReview } from '$lib/api/client';
  import { auth } from '$lib/stores/auth';
  import { formatCount, formatLongDate, formatLongDateTime } from '$lib/format';
  import { albumHref, artistHref, trackHref } from '$lib/links';
  import { reveal } from '$lib/reveal';
  import Cover from './Cover.svelte';
  import Genres from './Genres.svelte';
  import Decades from './Decades.svelte';
  import AlbumRuns from './AlbumRuns.svelte';

  let { year, token }: { year: number; token?: string } = $props();

  let data = $state<YearReview | null>(null);
  let years = $state<YearCount[]>([]);
  let status = $state<'loading' | 'ok' | 'missing' | 'error'>('loading');
  let shareUrl = $state<string | null>(null);
  let sharing = $state(false);
  let shareError = $state(false);
  let copied = $state(false);

  const base = $derived(token ? `/s/${token}` : '');
  const tz = $derived(token ? null : ($auth.user?.timezone ?? 'UTC'));
  const MONTHS = Array.from({ length: 12 }, (_, i) =>
    new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(2000, i, 1)))
  );

  $effect(() => {
    const client = statsApi(token);
    const wanted = year;
    status = 'loading';
    shareUrl = null;
    let cancelled = false;
    (async () => {
      try {
        const [review, all] = await Promise.all([
          client.year(wanted),
          client.years().catch(() => [] as YearCount[])
        ]);
        if (cancelled) return;
        data = review;
        years = all;
        status = 'ok';
      } catch (e) {
        if (cancelled) return;
        status = e instanceof ApiError && e.status === 404 ? 'missing' : 'error';
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  const listens = (n: number) => `${formatCount(n)} ${n === 1 ? 'listen' : 'listens'}`;
  const total = $derived(data?.summary.total_listens ?? 0);
  const hours = $derived(Math.round((data?.summary.total_seconds ?? 0) / 3600));
  const change = $derived.by(() => {
    const before = data?.previous?.total_listens;
    if (!before) return null;
    const pct = Math.round(((total - before) / before) * 100);
    return `${pct >= 0 ? '+' : ''}${pct}%`;
  });
  const maxMonth = $derived(Math.max(1, ...(data?.months ?? []).map((m) => m.listens)));
  const biggest = $derived(
    data ? data.months.reduce((a, b) => (b.listens > a.listens ? b : a), data.months[0]) : null
  );
  const lead = $derived(data?.top_artists[0] ?? null);
  const rest = $derived(data?.top_artists.slice(1) ?? []);

  function weekday(date: string): string {
    return new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' })
      .format(new Date(`${date}T12:00:00Z`));
  }
  const day = (date: string) => formatLongDate(`${date}T12:00:00`, null);

  async function share() {
    sharing = true;
    shareError = false;
    try {
      const created = await api.createShare({
        start: `${year}-01-01`, end: `${year + 1}-01-01`, label: `${year} in review`
      });
      shareUrl = `${location.origin}/s/${created.share_token}/year/${year}`;
    } catch {
      shareError = true;
    } finally {
      sharing = false;
    }
  }

  async function copy() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      copied = false;
    }
  }
</script>

{#if status === 'missing'}
  <p class="msg">This share does not cover {year}.</p>
{:else if status === 'error'}
  <p class="msg">Could not load this year. Please try again.</p>
{:else if status === 'ok' && data}
  <div class="review">
    {#if years.length > 1}
      <nav class="years" aria-label="Years">
        {#each years as y (y.year)}
          <a href="{base}/year/{y.year}" aria-current={y.year === year ? 'page' : undefined}>{y.year}</a>
        {/each}
      </nav>
    {/if}

    <section class="glass hero" aria-label={String(year)} use:reveal>
      <span class="eyebrow">{token ? 'a year in music' : 'your year in music'}</span>
      <h1>{year}</h1>
      {#if total > 0}
        <p class="big"><strong>{formatCount(total)}</strong> songs</p>
        <ul class="facts">
          {#if hours > 0}<li><strong>{formatCount(hours)}h</strong> of listening</li>{/if}
          <li><strong>{formatCount(data.summary.distinct_artists)}</strong> artists</li>
          <li><strong>{formatCount(data.summary.distinct_tracks)}</strong> tracks</li>
          <li><strong>{formatCount(data.summary.distinct_albums)}</strong> albums</li>
          {#if change}<li><strong>{change}</strong> on {year - 1}</li>{/if}
        </ul>
      {/if}
    </section>

    {#if total === 0}
      <p class="msg">No listens in {year}.</p>
    {:else}
      {#if lead}
        <section class="glass" aria-labelledby="y-artists" use:reveal>
          <h2 id="y-artists">Top artists</h2>
          <div class="lead">
            <Cover src={lead.image_url} alt="" size={150} />
            <div>
              <span class="rank">#1</span>
              <h3><a href={artistHref(base, lead.artist)}>{lead.artist}</a></h3>
              <p class="count">{listens(lead.count)}</p>
            </div>
          </div>
          {#if rest.length}
            <ol class="list" start="2">
              {#each rest as a (a.artist)}
                <li>
                  <a href={artistHref(base, a.artist)}><span class="name">{a.artist}</span></a>
                  <span class="count">{formatCount(a.count)}</span>
                </li>
              {/each}
            </ol>
          {/if}
        </section>
      {/if}

      <div class="pair">
        <section class="glass" aria-labelledby="y-tracks" use:reveal>
          <h2 id="y-tracks">Top tracks</h2>
          <ol class="list">
            {#each data.top_tracks as t (`${t.artist}\u0000${t.track}`)}
              <li>
                <a href={trackHref(base, t.artist, t.track)}>
                  <span class="name">{t.track}</span><span class="by">{t.artist}</span>
                </a>
                <span class="count">{formatCount(t.count)}</span>
              </li>
            {/each}
          </ol>
        </section>
        <section class="glass" aria-labelledby="y-albums" use:reveal>
          <h2 id="y-albums">Top albums</h2>
          <ol class="list covers">
            {#each data.top_albums as a (`${a.artist}\u0000${a.album}`)}
              <li>
                <Cover src={a.image_url} alt="" size={36} />
                {#if a.album}
                  <a href={albumHref(base, a.artist, a.album)}>
                    <span class="name">{a.album}</span><span class="by">{a.artist}</span>
                  </a>
                {/if}
                <span class="count">{formatCount(a.count)}</span>
              </li>
            {/each}
          </ol>
        </section>
      </div>

      <section class="glass" aria-labelledby="y-months" use:reveal>
        <h2 id="y-months">Month by month</h2>
        {#if biggest && biggest.listens > 0}
          <p class="caption">
            Your biggest month was {MONTHS[biggest.month - 1]}, with {listens(biggest.listens)}{#if biggest.top_artist}, most of all {biggest.top_artist}{/if}.
          </p>
        {/if}
        <ol class="months">
          {#each data.months as m (m.month)}
            <li aria-label="{MONTHS[m.month - 1]}: {listens(m.listens)}" class:top={m === biggest}>
              <span class="value">{formatCount(m.listens)}</span>
              <span class="bar" style="--h: {(m.listens / maxMonth) * 100}%"></span>
              <span class="label">{MONTHS[m.month - 1].slice(0, 3)}</span>
              <span class="who">{m.top_artist ?? ''}</span>
            </li>
          {/each}
        </ol>
      </section>

      <div class="pair">
        {#if data.busiest_day}
          <section class="glass moment" aria-labelledby="y-day" use:reveal>
            <h2 id="y-day">Busiest day</h2>
            <p class="when">{weekday(data.busiest_day.date)}, {day(data.busiest_day.date)}</p>
            <p class="big"><strong>{formatCount(data.busiest_day.listens)}</strong> listens</p>
            {#if data.busiest_day.top_artist}
              <p class="note">Mostly <a href={artistHref(base, data.busiest_day.top_artist)}>{data.busiest_day.top_artist}</a>.</p>
            {/if}
          </section>
        {/if}
        {#if data.longest_streak}
          <section class="glass moment" aria-labelledby="y-streak" use:reveal>
            <h2 id="y-streak">Longest streak</h2>
            <p class="big"><strong>{formatCount(data.longest_streak.days)}</strong> {data.longest_streak.days === 1 ? 'day' : 'days'}</p>
            <p class="note">in a row with music, {day(data.longest_streak.start)} to {day(data.longest_streak.end)}.</p>
          </section>
        {/if}
      </div>

      {#if data.first_listen && data.last_listen}
        <section class="glass" aria-labelledby="y-ends" use:reveal>
          <h2 id="y-ends">First and last</h2>
          <div class="ends">
            {#each [{ label: 'The year began with', l: data.first_listen }, { label: 'and ended with', l: data.last_listen }] as e (e.label)}
              <div class="end">
                <Cover src={e.l.image_url} alt="" size={64} />
                <div>
                  <span class="eyebrow">{e.label}</span>
                  <a href={trackHref(base, e.l.artist, e.l.track)} class="name">{e.l.track}</a>
                  <span class="by">{e.l.artist}</span>
                  <span class="stamp">{formatLongDateTime(e.l.played_at, tz)}</span>
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/if}

      <section class="glass" aria-labelledby="y-new" use:reveal>
        <h2 id="y-new">New to you</h2>
        {#if data.new_artists.count === 0}
          <p class="note">No artist you had not heard before.</p>
        {:else}
          <p class="big">
            <strong>{formatCount(data.new_artists.count)}</strong>
            {data.new_artists.count === 1 ? 'artist' : 'artists'} you heard for the first time
          </p>
          <ol class="list">
            {#each data.new_artists.top as a (a.artist)}
              <li>
                <a href={artistHref(base, a.artist)}>
                  <span class="name">{a.artist}</span>
                  <span class="by">since {formatLongDate(a.first_listen, tz)}</span>
                </a>
                <span class="count">{formatCount(a.listens)}</span>
              </li>
            {/each}
          </ol>
        {/if}
      </section>

      {#if data.genres.artists > 0 || data.decades.known > 0}
        <div class="pair" use:reveal>
          <Genres genres={data.genres} {base} />
          <Decades decades={data.decades} />
        </div>
      {/if}

      {#if data.album_runs.total > 0}
        <div use:reveal><AlbumRuns runs={data.album_runs} {base} {tz} /></div>
      {/if}

      <section class="glass outro" aria-labelledby="y-end" use:reveal>
        <h2 id="y-end">That was {year}.</h2>
        {#if !token}
          {#if shareUrl}
            <div class="share">
              <input type="text" readonly value={shareUrl} aria-label="Share link" onfocus={(e) => e.currentTarget.select()} />
              <button type="button" onclick={copy}>{copied ? 'Copied' : 'Copy'}</button>
            </div>
            <p class="note">Anyone with this link sees {year} as you see it here. Revoke it under Share.</p>
          {:else}
            <button type="button" class="primary" onclick={share} disabled={sharing}>Share this year</button>
          {/if}
          {#if shareError}<p class="error" role="alert">Could not create the link.</p>{/if}
        {/if}
      </section>
    {/if}
  </div>
{/if}

<style>
  .review {
    max-width: 980px;
    margin: 0 auto;
    padding: calc(var(--viewport-r) + 16px) clamp(1rem, 4vw, 2rem) 4rem;
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
  }
  section {
    padding: 1.4rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    min-width: 0;
  }
  h2 {
    font-size: 1.35rem;
  }
  .review :global(.reveal) {
    opacity: 0;
    transform: translateY(18px);
    transition:
      opacity 500ms var(--ease-out),
      transform 600ms var(--ease-spring);
  }
  .review :global(.reveal.shown) {
    opacity: 1;
    transform: none;
  }
  .years {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    justify-content: center;
  }
  .years a {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    padding: 0.3rem 0.7rem;
    border-radius: var(--r-xs);
    color: var(--text-muted);
    text-decoration: none;
  }
  .years a:hover {
    color: var(--text);
  }
  .years a[aria-current='page'] {
    background: var(--surface0);
    color: var(--text);
  }
  .hero {
    align-items: center;
    text-align: center;
    padding: 2.6rem 1.5rem 2.2rem;
    gap: 0.6rem;
  }
  .hero h1 {
    font-size: clamp(4rem, 16vw, 8.5rem);
    line-height: 0.95;
    color: var(--accent-text);
    letter-spacing: -0.06em;
  }
  .big {
    margin: 0;
    font-size: 1.05rem;
    color: var(--text-muted);
  }
  .big strong {
    font-family: var(--font-display);
    font-size: 2.2rem;
    color: var(--text);
    letter-spacing: -0.03em;
    margin-right: 0.25rem;
  }
  .hero .big strong {
    font-size: clamp(2.4rem, 8vw, 3.4rem);
  }
  .facts {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.4rem 1.4rem;
    font-size: 0.85rem;
    color: var(--text-muted);
  }
  .facts strong {
    color: var(--text);
  }
  .lead {
    display: flex;
    gap: 1.2rem;
    align-items: center;
  }
  .lead :global(img),
  .lead :global(.placeholder) {
    border-radius: var(--r-sm);
  }
  .lead h3 {
    font-size: clamp(1.4rem, 5vw, 2.2rem);
    overflow-wrap: anywhere;
  }
  .lead h3 a {
    color: var(--text);
    text-decoration: none;
  }
  .lead h3 a:hover {
    color: var(--accent-text);
  }
  .rank {
    font-family: var(--font-mono);
    color: var(--accent-text);
    font-size: 0.9rem;
  }
  .lead .count {
    margin: 0.3rem 0 0;
  }
  .list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .list li {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-xs);
    min-width: 0;
  }
  .list li:nth-child(odd) {
    background: var(--mantle);
  }
  .list a {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    color: var(--text);
    text-decoration: none;
  }
  .list a:hover .name {
    color: var(--accent-text);
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.9rem;
  }
  .by {
    font-size: 0.72rem;
    color: var(--text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .count {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .pair {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
    gap: 1.1rem;
  }
  .caption,
  .note {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
    line-height: 1.5;
  }
  .note a {
    color: var(--text);
  }
  .months {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 0.4rem;
    height: 15rem;
    align-items: end;
  }
  .months li {
    height: 100%;
    display: grid;
    grid-template-rows: auto 1fr auto auto;
    align-items: end;
    justify-items: center;
    gap: 0.25rem;
    min-width: 0;
  }
  .months .value {
    grid-row: 1;
  }
  .months .label {
    grid-row: 3;
  }
  .months .who {
    grid-row: 4;
  }
  .months .bar {
    grid-row: 2;
    width: 100%;
    max-width: 2.6rem;
    height: max(var(--h), 3px);
    align-self: end;
    border-radius: var(--r-xs) var(--r-xs) 0 0;
    background: var(--surface1);
  }
  .months li.top .bar {
    background: var(--accent);
  }
  .months .value {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--text-dim);
    align-self: end;
  }
  .months .label {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-muted);
  }
  .months .who {
    font-size: 0.6rem;
    color: var(--text-dim);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-height: 1em;
  }
  @media (max-width: 640px) {
    .lead :global(img),
    .lead :global(.placeholder) {
      width: 96px !important;
      height: 96px !important;
    }
    .months {
      height: 12rem;
      gap: 0.2rem;
    }
    .months .value,
    .months .who {
      display: none;
    }
  }
  .moment .when {
    margin: 0;
    font-size: 0.95rem;
  }
  .ends {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
    gap: 0.9rem;
  }
  .end {
    display: flex;
    gap: 0.9rem;
    align-items: center;
    padding: 0.8rem;
    border-radius: var(--r-sm);
    background: var(--mantle);
    min-width: 0;
  }
  .end > div {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    min-width: 0;
  }
  .end .name {
    color: var(--text);
    text-decoration: none;
    font-weight: 600;
  }
  .end .name:hover {
    color: var(--accent-text);
  }
  .stamp {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-dim);
  }
  .outro {
    align-items: center;
    text-align: center;
    padding: 2rem 1.5rem;
  }
  .outro h2 {
    font-size: 1.8rem;
  }
  .share {
    display: flex;
    gap: 0.5rem;
    width: min(100%, 34rem);
  }
  .share input {
    flex: 1;
    min-width: 0;
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.45rem 0.65rem;
    font-family: var(--font-mono);
    font-size: 0.78rem;
  }
  button {
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    padding: 0.45rem 0.95rem;
    font-size: 0.85rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  button:hover:not(:disabled) {
    background: var(--surface1);
  }
  button:focus-visible,
  input:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-text);
  }
  button:disabled {
    opacity: 0.55;
  }
  .primary,
  .primary:hover:not(:disabled) {
    background: var(--accent);
    color: var(--accent-contrast);
  }
  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.85rem;
  }
  .msg {
    text-align: center;
    padding: 3rem 1.5rem;
    color: var(--text-muted);
    margin: 0;
  }
</style>
