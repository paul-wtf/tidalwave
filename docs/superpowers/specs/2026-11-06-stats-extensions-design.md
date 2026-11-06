# Stats extensions: design

## Intent

tidalwave answers "what did I listen to" well and "what does it mean" poorly.
Clock and weekday are off by the UTC offset, ranges are only rolling windows,
top lists end in an external search, and nothing shows how listening changes.
This round fixes the numbers that are wrong today and adds the views that make
the existing data worth coming back to: detail pages, covers, comparisons and
an insights page.

Success: a user in Europe/Berlin sees their clock in local time, can pick
"October 2026", clicks an artist and lands on a page about that artist with
covers, and finds streaks, discoveries, a heatmap and "on this day" on one page.
Every view works the same through a share link, limited to the share's range.

## Scope

In:

0. Album identity fix (prerequisite)
1. Per-user timezone
2. Share management
3. Sync status and reconnect banner
4. Calendar and custom ranges
5. Comparison with the previous period
6. Detail pages for artist, album and track
7. Album covers
8. Discoveries
9. Streaks and records
10. Listening heatmap
11. On this day

Non-goals: genres, a Wrapped-style year review, now-playing, ListenBrainz, an
admin UI, data export, account deletion. Not touched either: the first connect
still ingests the full history in one background task. That is a separate
problem and stays out of this change.

Anti-goals:

- No new infrastructure. No Redis, no job queue, no image proxy.
- No new ingress prefixes. Every new endpoint lives under `/auth`, `/stats`,
  `/shares` or `/shared`, because the Helm chart routes exactly those four to
  the backend (`helm/tidalwave/templates/ingress.yaml`).
- A share link must never reveal data outside its range, its owner's
  username excepted.

## 0. Album identity

An album is `(artist, album)`, not `album`. Today `top_albums` and the
`distinct_albums`/`albums` counts in `summary_stats` and `metrics_over_time`
group by name only, so "Greatest Hits" by two artists becomes one row.

- `top_albums` groups by `(artist, album)` and returns `artist` on every row,
  like `top_tracks` already does.
- Distinct album counts count `(artist, album)` pairs.
- Listens with `album IS NULL` stay excluded from album counts. They still
  appear as an "Unknown album" row in the top list, but no longer as a single
  row: they split by artist like everything else. *(My call; the alternative
  of dropping that row entirely is a one-line change.)*

Scrobbles carry the track artist, not the album artist, so a compilation by
various artists splits into one album per artist. That is accepted; Last.fm
gives us nothing better.

## 1. Timezone

- New column `users.timezone`: IANA name, nullable. NULL means "not set yet"
  and is treated as UTC.
- `/auth/me` returns it. New `PATCH /auth/me` with `{"timezone": "<IANA>"}`;
  the name is validated with `zoneinfo.ZoneInfo`, 422 if unknown.
- On login, if `timezone` is NULL, the frontend sends the browser's
  `Intl.DateTimeFormat().resolvedOptions().timeZone` once. After that it only
  changes through the settings menu (item 3).
- Every query that turns an instant into a calendar value uses the user's
  timezone instead of `'UTC'`: hour of day, weekday, `date_trunc` buckets,
  calendar range boundaries, day-based records and the heatmap.
- Shared views use the share owner's timezone.

## 2. Share management

- New column `shares.label` (text, nullable).
- `POST /shares` takes an optional JSON body
  `{"label": str?, "range_from": datetime?, "range_to": datetime?}`.
  An empty or missing body behaves like today.
- New `GET /shares` lists the user's non-revoked shares: token, label, range
  and `created_at`, newest first.
- `DELETE /shares/{token}` stays as it is.
- `ShareManager` becomes a popover: the list of active shares (label or
  "Untitled", range or "All time", copy and revoke per row) and a form to
  create one. The form offers "All time" or the currently selected range.
  A share for a rolling range stores the resolved instants at creation time,
  so "Last 30 days" is frozen to the 30 days before it was created. *(My call:
  a moving share window would need a new range model on `shares`.)*
- Revoking from the list is the only way. Reloading the page no longer loses
  anything because the list comes from the server.

## 3. Sync status and reconnect

- The poller sets `sync_state.last_synced_at` on every successful poll of a
  user, not only when new scrobbles arrived. `last_played_at` keeps its current
  meaning.
- `/auth/me` additionally returns `disconnected`, `last_synced_at` and
  `last_played_at` (the latter two nullable).
- A new settings menu in the header (behind the username) shows: the username,
  "Synced 3 min ago" (or "Importing your history…" while no `sync_state` row
  exists), the timezone picker and a logout button.
- If `disconnected` is true, a banner above the content says that Last.fm
  access was revoked and offers "Reconnect", which goes to `/auth/login`.
  The existing callback already clears the flag on reconnect.

## 4. Calendar and custom ranges

The range selector keeps its rolling options and gains calendar ones:

- Rolling: Last 24 hours, Last 7 days, Last 30 days, Last 365 days, All time.
  The existing labels "Day", "Week", "Month", "Year" become these more honest
  ones.
- Calendar: This week, This month, This year, Last week, Last month,
  Last year.
- Custom: a from and a to date, both inclusive.

Calendar boundaries are local midnight in the user's timezone; weeks start on
Monday. Because the browser's timezone may differ from the user's setting, the
backend resolves calendar ranges, not the frontend. The mechanism is the
builder's choice. A suggestion: every stats endpoint accepts `start`/`end` as
local dates (`YYYY-MM-DD`, `end` exclusive) as an alternative to
`since`/`until`, and the frontend maps "This month" to dates in the user's
timezone, which it knows from `/auth/me`.

The selection is persisted like today (localStorage) and read from a single
store, so every page follows it. A stored value from the old format maps to
the matching rolling option.

Share views keep a fixed range and show no selector, as today.

## 5. Comparison with the previous period

- The four stat cards on the overview show the change against the previous
  period, e.g. "+12 % vs. previous", coloured up/down, hidden when the previous
  value is 0.
- Previous period: for rolling ranges the window of equal length right before
  it. For calendar ranges the same elapsed span of the previous calendar
  period: on 6 November, "This month" compares 1 to 6 November with 1 to 6 October.
  A completed calendar range ("Last month") compares with the full month
  before it. Custom ranges compare with the equal-length window before them.
  All time has no comparison.
- The backend computes the previous period, so the timezone rules from item 1
  apply. Suggested shape: `GET /stats/summary?…&compare=true` returns the
  current summary plus a `previous` object of the same shape.
- No comparison in share views: the previous period lies outside the share's
  range.

## 6. Detail pages

Three new pages, reachable from every top list, the recent list and from each
other. Identity goes in query parameters, because names contain slashes and
other characters that are awkward in path segments:

- `/artist?artist=<name>`
- `/album?artist=<name>&album=<name>`
- `/track?artist=<name>&track=<name>`

Each also exists under `/s/<token>/…` for shares.

Content, with counts and lists following the selected range:

- Artist: cover (item 7), listens, time listened, rank among artists in the
  range, first and last listen, listens over time, top tracks, top albums, the
  artist's most recent listens.
- Album: cover, artist link, listens, time listened, first and last listen,
  listens over time, its tracks ranked by listens.
- Track: cover of its most-listened album, artist and album links, listens,
  time listened, first and last listen, listens over time, recent plays.

First and last listen are all-time values, not range values, because "first
heard in 2019" is the point of the field. In share views they are clamped to
the share's range.

The platform search icons stay on every row and on each detail page header.
The label itself now links to the detail page.

Suggested backend shape: `GET /stats/artist`, `/stats/album`, `/stats/track`
returning one object each, plus a `artist`/`album` filter on the existing top
and over-time queries where that avoids new SQL. A detail page for a name with
no listens returns 404 and the page says so.

## 7. Album covers

- `user.getRecentTracks` already returns an `image` array per track; the client
  discards it today. Ingest keeps the `extralarge` URL.
- New table `album_art`: `(artist, album)` unique, `image_url` nullable,
  `fetched_at`. Like `track_durations`, a row with NULL means "asked, none
  available" and is not asked again.
- Ingest upserts covers it saw; a non-empty URL wins over NULL, a newer URL
  replaces an older one.
- Last.fm returns a placeholder for missing art. URLs containing its hash
  `2a96cbd8b46e442fc41c2b86b821562f` are stored as NULL.
- Existing data is filled through `album.getInfo`, budgeted per poll run like
  durations (`_POLL_DURATION_BUDGET` in `cli.py`), plus a CLI
  `tidalwave-backfill-covers` mirroring `tidalwave-backfill-durations`.
- Last.fm stopped serving artist images in 2019. An artist's picture is the
  cover of their most-listened album in the range.
- The browser loads images straight from Last.fm's CDN. Every image has a
  neutral placeholder when the URL is NULL or fails to load.
- Covers appear in top lists (album and artist rows), the recent list and the
  detail pages. Top-list endpoints return `image_url` per row.

## 8. Discoveries

For the selected range:

- New artists: artists whose first-ever listen falls inside the range, with
  that date and their listens in the range, ordered by listens.
- New tracks: count, plus the top ones by listens.
- Rediscoveries: artists listened to in the range whose previous listen before
  the range start is at least 180 days earlier, with the gap length.
  *(180 days is my call.)*

"First-ever" in a share view means first inside the share's range.

## 9. Streaks and records

Days are calendar days in the user's timezone.

- Longest streak in the range: most consecutive days with at least one listen,
  with start and end date.
- Current streak: consecutive days up to today (or yesterday, if today has no
  listen yet). Shown only when the range includes today.
- Busiest day in the range: date and listen count.
- Longest session in the range: a run of listens where each starts at most
  30 minutes after the previous one; shown with start, length in listens and
  time listened. *(30 minutes is my call.)*

## 10. Listening heatmap

A calendar grid of days, one column per week, cells shaded by listen count in
five steps, tooltip with date and count. It shows the selected range when that
range is at most 366 days long, otherwise the 365 days ending at the range end.
Uses the user's timezone for day boundaries.

## 11. On this day

Listens on today's calendar date in each previous year that has any: the year,
the listen count and the top three tracks of that day. This section ignores
the selected range; in share views it only shows years inside the share's
range.

## Where things go in the UI

- Overview: unchanged layout, plus the comparison on the stat cards (item 5).
- New nav entry "Insights" (`/insights`, `/s/<token>/insights`) with, in
  order: on this day, streaks and records, heatmap, discoveries.
- Header: range selector, share popover, settings menu, theme toggle.

## Constraints

- Share views and own views run the same queries. Today every stats route has
  a hand-written twin in `routes/share.py`; with this many new endpoints the
  builder should replace that with a shared scope dependency (user id, range
  clamp, timezone) resolved from either the session or the share token, and
  mount one router under both `/stats` and `/shared/{token}`. Existing URLs and
  response shapes stay valid except where this spec changes them.
- Alembic migrations for `users.timezone`, `shares.label` and `album_art`.
- `backend/openapi.json` and `frontend/src/lib/api/schema.d.ts` are regenerated;
  CI checks the schema for drift.
- Stats `limit` parameters get an upper bound (500).
- Tests: backend queries and routes with pytest against Postgres, including
  share-range clamping for every new endpoint; component tests with Vitest for
  new components; the Playwright smoke test keeps passing.
- Design language stays Catppuccin with the existing tokens; no chart or UI
  library is added.

## Edge cases (my calls)

- Ranges are half-open everywhere: `[from, to)` as instants, exactly like
  today's `since`/`until` (`played_at < until`). `shares.range_to` is
  exclusive. A custom range's inclusive "to" date becomes the following local
  midnight.
- Share views may narrow a range but never widen it. Shared endpoints accept the same
  range parameters as own ones; the scope dependency intersects them with the
  share's range. The share frontend sends none, so it sees the full share range.
- Shares hold instants. Changing the timezone later does not move an
  existing share's range. NULL timezone means UTC, also for shares.
- "Today" is the owner's today. Current streak and on this day are
  evaluated at request time in the owner's timezone, in share views too.
- `album_art` is global, like `track_durations`. Covers are only joined
  onto rows that are already in scope, and the artist picture is computed
  in scope too.
- On detail pages, rank is the position in the range's top list, using the
  same ordering (count desc, then name). 404 only when the entity has no
  listens in scope at all (all time for own views, the share range for
  shares). An artist with listens outside the selected range renders with zero
  counts and its all-time first and last listen.
- "Unknown album" rows have no album page. Their label is plain text; the
  artist link and platform icons stay.
- Responses change additively. New fields on existing responses are fine;
  existing `/stats/…` and `/shared/{token}/…` paths and fields stay.
- Nothing is cached. Streaks, sessions, heatmap and discoveries are computed per
  request. The migration adds an index on `listens (user_id, artist,
  played_at)` for the first/previous-listen lookups.
- The stored range is the symbolic option (`this_month`, `rolling_30d`, …);
  a custom range stores its two dates.

## Left to the builder

Query implementation, component structure, exact copy, loading and empty
states, the heatmap's colour steps, the mechanism for calendar ranges and
comparisons within the constraints above, and how the PR's commits are cut.
