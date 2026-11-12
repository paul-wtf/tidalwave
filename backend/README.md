# tidalwave — backend

tidalwave is a self-hosted, multi-user listening tracker for Tidal. Because Tidal does not expose a listening-history API, users scrobble their Tidal plays to Last.fm (via the Tidal app or a scrobbler) and tidalwave pulls that history through the Last.fm `user.getRecentTracks` API. The backend is a FastAPI service backed by PostgreSQL; it handles Last.fm OAuth-style authentication, per-user scrobble ingestion, stats aggregation, and shareable read-only links.

---

## Local development

**Prerequisites:** [uv](https://docs.astral.sh/uv/) and a running PostgreSQL instance.

The easiest way to get Postgres is via Docker Compose:

```bash
docker-compose up -d        # starts postgres:16 on localhost:5432
```

Then install dependencies, run migrations, and start the dev server:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn tidalwave.main:app --reload --port 8080
```

The API is now available at `http://localhost:8080`.

---

## Environment variables

All settings are read from environment variables prefixed with `TIDALWAVE_` (or from a `.env` file in the working directory).

| Variable | Default | Description |
|---|---|---|
| `TIDALWAVE_DATABASE_URL` | `postgresql+asyncpg://tidalwave:tidalwave@localhost:5432/tidalwave` | Async SQLAlchemy connection URL for PostgreSQL. |
| `TIDALWAVE_LASTFM_API_KEY` | *(empty)* | Last.fm API key. Obtain one at https://www.last.fm/api/account/create. |
| `TIDALWAVE_LASTFM_API_SECRET` | *(empty)* | Last.fm API secret corresponding to the key above. |
| `TIDALWAVE_PUBLIC_BASE_URL` | `http://localhost:8080` | Public base URL of this service. Used to build the `cb=` callback parameter sent to Last.fm during auth. Must be reachable by the browser completing the OAuth flow. |
| `TIDALWAVE_REGISTRATION_MODE` | `allowlist` | Controls who may connect a Last.fm account. `open` allows anyone; `allowlist` restricts to the usernames listed in `TIDALWAVE_REGISTRATION_ALLOWLIST`. |
| `TIDALWAVE_REGISTRATION_ALLOWLIST` | *(empty)* | Comma-separated list of Last.fm usernames permitted to register when `REGISTRATION_MODE=allowlist`. Example: `alice,bob`. Admins can allow more names at runtime on the admin page; those are stored in the database. A name on either list may register, compared without regard to case. |
| `TIDALWAVE_SESSION_SECRET` | `dev-insecure-change-me` | Secret used to sign the session cookie with itsdangerous. **Must be set to a strong random value in production.** |
| `TIDALWAVE_FRONTEND_URL` | *(empty)* | Base URL the backend fetches the frontend's `index.html` from, to serve `/s/<token>` with link-preview tags. Needs the ingress to route `/s/` to the backend. Empty: `/s/<token>` on the backend answers with a small page that carries the tags and forwards to `/?share=<token>`. |
| `TIDALWAVE_LINKHOP_URL` | *(empty)* | Base URL of a [linkhop](https://github.com/paul-wtf/linkhop) instance, `http://` or `https://`. When set, the frontend shows one more icon next to the platform links, which opens `<url>/?q=<artist title>` there. Empty: no icon. |
| `TIDALWAVE_MUSICBRAINZ_URL` | `https://musicbrainz.org/ws/2` | Base URL of the MusicBrainz API, which the poll asks for album release years. Point it at a mirror if you run one. |
| `TIDALWAVE_MUSICBRAINZ_BUDGET` | `30` | Albums whose release year one poll run looks up. MusicBrainz allows one request per second and an album takes one or two, so 30 albums add up to a minute to a run. `0` turns the lookups off. |
| `TIDALWAVE_IMPORT_MAX_BYTES` | `104857600` | Largest history file a user may upload to `/imports`, 100 MB by default. Larger uploads get 413. A zip may unpack to twenty times this. |
| `TIDALWAVE_IMPORT_DIR` | *(empty)* | Directory where uploads wait while they are imported; each file is deleted when its import ends. Empty: the system temp directory. |
| `TIDALWAVE_LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## Last.fm connect flow

1. Register a Last.fm API account at https://www.last.fm/api/account/create to obtain an API key and secret. Set `TIDALWAVE_LASTFM_API_KEY` and `TIDALWAVE_LASTFM_API_SECRET`.
2. A user visits `GET /auth/login`. The server redirects the browser to Last.fm's authorization page.
3. Last.fm redirects back to `GET /auth/callback?token=<token>`. The server exchanges the one-time token for a permanent session key, then creates or logs in the user via `upsert_user_from_session`.
4. The first user to connect automatically becomes admin. Subsequent registrations are gated by `TIDALWAVE_REGISTRATION_MODE`; a 403 is returned if the Last.fm username is not on the allowlist when mode is `allowlist`.
5. On success the server sets an `httponly` session cookie and redirects to `/`.
6. `POST /auth/logout` clears the cookie.

---

## Endpoints

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Returns `{"status": "ok"}`. |

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/auth/login` | None | Redirects to Last.fm authorization page. |
| `GET` | `/auth/callback` | None | Receives Last.fm token, creates/logs in user, sets session cookie. |
| `POST` | `/auth/logout` | None | Clears session cookie. |
| `GET` | `/auth/config` | None | Settings the static frontend reads at start, also in share views: `{"linkhop_url": <url or null>}`. |
| `GET` | `/auth/me` | Session | Username, admin flag, timezone, `disconnected`, `last_synced_at`, `last_played_at` and `weekly_report_webhook`, the saved Discord webhook masked (`https://discord.com/api/webhooks/1234…/…wxyz`) or `null`. |
| `PATCH` | `/auth/me` | Session | Sets the timezone: `{"timezone": "<IANA name>"}`, 422 for an unknown name. |
| `PUT` | `/auth/me/webhook` | Session | Saves the Discord webhook for the weekly report: `{"url": "https://discord.com/api/webhooks/<id>/<token>"}`. `discordapp.com` works as well; any other address is a 422. Returns the same body as `GET /auth/me`. |
| `DELETE` | `/auth/me/webhook` | Session | Clears the webhook. Returns the same body as `GET /auth/me`. |
| `POST` | `/auth/me/webhook/test` | Session | Posts a short test message to the saved webhook. 204 on success, 409 without a webhook, 502 when Discord refuses it or cannot be reached. |
| `DELETE` | `/auth/me` | Session | Deletes the user with their listens, shares, comparisons, invites and sync state, and clears the session cookie. The shared `album_art` and `track_durations` caches stay. |
| `GET` | `/auth/export` | Session | Streams every listen of the user as a download. `format=csv` or `format=json`; fields: `played_at` (ISO-8601, UTC), `artist`, `track`, `album`, `track_mbid`, `artist_mbid`, `album_mbid`, `duration_sec`. |

### Stats (session-gated, requires a valid session cookie)

Every endpoint takes a range, either as instants (`since`, `until`: ISO-8601
datetimes, `until` exclusive) or as local dates in the user's timezone
(`start`, `end`: `YYYY-MM-DD`, `end` exclusive). Mixing the two is a 422.
Hours, weekdays, days and period buckets are computed in the user's timezone
(UTC until one is set). `limit` is capped at 500.

| Method | Path | Extra query params | Description |
|---|---|---|---|
| `GET` | `/stats/summary` | `compare`, `calendar` (`week`\|`month`\|`year`) | `total_listens`, `distinct_artists`, `distinct_tracks`, `distinct_albums`, `total_seconds`. With `compare=true` also `previous`, the same totals for the period before (`null` for all time). |
| `GET` | `/stats/top-artists` | `limit` (default 20), `genre` | Top artists by listen count, each with the cover of their most-listened album. `genre` keeps the artists with that tag. |
| `GET` | `/stats/top-tracks` | `limit`, `artist`, `album`, `track` | Top tracks by listen count. |
| `GET` | `/stats/top-albums` | `limit`, `artist`, `album`, `track` | Top albums by listen count, keyed by `(artist, album)`, with cover. |
| `GET` | `/stats/recent` | `limit` (default 50), `artist`, `album`, `track` | Most recent listens. |
| `GET` | `/stats/clock` | | 24 listen counts by hour of day. |
| `GET` | `/stats/weekday` | | 7 listen counts by ISO weekday (index 0 = Monday). |
| `GET` | `/stats/hour-weekday` | | 7 rows (Monday to Sunday) of 24 hourly listen counts. |
| `GET` | `/stats/history` | `bucket` (`day`\|`week`\|`month`, default `day`) | Chronological series: `[{"period": <iso>, "count": N}]`. |
| `GET` | `/stats/metrics-over-time` | `bucket`, `artist`, `album`, `track`, `genre` | Per period: listens, distinct artists and albums, seconds. `genre` keeps the listens of artists with that tag. |
| `GET` | `/stats/search` | `q` | Up to five artists, albums and tracks whose name contains `q`, ignoring case. Ordered by listens in the range, then by listens overall; `count` is the listens in the range. |
| `GET` | `/stats/artist` | `artist` | Detail for one artist: listens, seconds, rank, first and last listen, cover. 404 without any listen. |
| `GET` | `/stats/album` | `artist`, `album` | Detail for one album. |
| `GET` | `/stats/track` | `artist`, `track` | Detail for one track, with its most-listened album. |
| `GET` | `/stats/artist-race` | `bucket` (`day`\|`week`\|`month`), `limit` (default 10) | The whole race of the top artists in one response: `{"bucket", "periods": [<iso>], "artists": [{"artist", "image_url", "totals": [N per period]}]}`. `totals` are running listen counts since the start of the range. It lists every artist that is among the top `limit` at the end of some period, so ranking them by their total at a period gives the top `limit` of that period. Without `bucket` the server picks days for ranges up to 92 days and months beyond. |
| `GET` | `/stats/album-runs` | `limit`, `artist`, `album` | Times an album was played through, newest first: `{"total": N, "runs": [{"artist", "album", "started_at", "tracks", "listens", "seconds", "image_url"}]}`. A run is at least six different tracks of one album in a row with pauses of at most ten minutes, a heuristic, because Last.fm does not say how many tracks an album has. `artist` and `album` keep the runs of one album. |
| `GET` | `/stats/decades` | | Listens by the decade their album first came out: `{"decades": [{"decade": 1990, "listens": N}], "known": N, "unknown": N, "pending": N}`. Decades between the first and the last one are listed even when empty. `unknown` counts the listens without a known year, and `pending` the part of them that carries a MusicBrainz id and has not been looked up yet. |
| `GET` | `/stats/discoveries` | `limit` | New artists, new tracks and rediscoveries in the range. |
| `GET` | `/stats/genres` | `limit` | Genres ranked by the listens of their artists: `{"genres": [{"genre", "listens", "artists"}], "artists": N, "tagged_artists": M}`. An artist's listens count in full for each of its first three tags. `artists` is the number of artists in the range and `tagged_artists` how many of them have been looked up on Last.fm, so a client can tell when the ranking is still filling in. |
| `GET` | `/stats/genre` | `genre` | Totals for one genre in the range: listens, seconds and artists. 404 when no artist the user has listened to carries the tag among its first three. |
| `GET` | `/stats/records` | | Longest and current streak, busiest day, longest session. |
| `GET` | `/stats/heatmap` | | Listens per day, at most 366 days. |
| `GET` | `/stats/on-this-day` | | Listens on today's date in earlier years. Ignores the range parameters. |
| `GET` | `/stats/now-playing` | | The track Last.fm reports as playing right now (`track`, `artist`, `album`, `image_url`), or `null`. Takes no range. The answer is kept in memory for 15 seconds per user, and a Last.fm failure yields `null`. |
| `GET` | `/stats/milestones` | | Round listen counts reached so far and the next one. Ignores the range parameters. |
| `GET` | `/stats/sources` | | Imported listens in the range: `{"imported", "imported_before_lastfm", "lastfm_first", "sources": [{"source", "listens"}]}`. `imported_before_lastfm` counts the ones older than the first listen from Last.fm. |
| `GET` | `/stats/years` | | The years with listens, newest first: `[{"year", "listens"}]`, in the user's timezone. Ignores the range parameters. |
| `GET` | `/stats/year/{year}` | | Everything the year in review shows, in one response: `summary`, `previous` (last year's summary), `top_artists`, `top_tracks`, `top_albums` (ten each), `months` (twelve, each with `listens`, `seconds`, `artists`, `top_artist`), `busiest_day` (`date`, `listens`, `top_artist`), `first_listen` and `last_listen`, `new_artists` (`count`, `top`), `genres`, `decades`, `longest_streak` and `album_runs`, all for the calendar year in the user's timezone. Ignores the range parameters. A year without listens returns zeros and `null`s. |

### Admin (admins only)

Every route answers 401 without a session and 403 for users who are not
admins. The first user to connect is the admin.

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/admin/users` | Every account: `id`, `username`, `is_admin`, `disconnected`, `created_at`, `listens` and `last_synced_at`, the time of the last successful poll or `null`. |
| `DELETE` | `/auth/admin/users/{id}` | Deletes another account the way `DELETE /auth/me` does. 409 for the admin's own id, 404 for an unknown one. |
| `GET` | `/auth/admin/allowlist` | `{"mode": "open"\|"allowlist", "entries": [{"username", "fixed", "added_at"}]}`. `fixed` entries come from `TIDALWAVE_REGISTRATION_ALLOWLIST`. |
| `POST` | `/auth/admin/allowlist` | Adds `{"username": "..."}` (letters, digits, `_`, `.`, `-`, at most 64). 409 when the name is already on either list, in any case. |
| `DELETE` | `/auth/admin/allowlist/{username}` | Removes a name added at runtime. 409 for a name from the environment, 404 for an unknown one. Existing accounts stay. |

### Comparisons (session-gated)

Two users see each other's listening only after one of them accepted the
other's invite. Either side can end it.

| Method | Path | Description |
|---|---|---|
| `GET` | `/comparisons` | `{"pairs": [{"id", "partner", "created_at"}], "invites": [{"token", "created_at"}]}`, the open invites being the user's own. |
| `POST` | `/comparisons/invites` | Creates an invite token. It works once. |
| `GET` | `/comparisons/invites/{token}` | `{"inviter", "own"}` for an open invite, 404 for a used, revoked or unknown one. |
| `POST` | `/comparisons/invites/{token}/accept` | Stores the pair and returns it. 409 for one's own invite or when the two already compare; the invite then stays open. |
| `DELETE` | `/comparisons/invites/{token}` | Revokes one of the user's open invites. |
| `GET` | `/comparisons/{id}` | Takes the range parameters of `/stats`, resolved in the viewer's timezone, and `limit` (default 10, at most 50). Returns `overlap`, `listens` (`you`, `partner`), `shared_artists`, `shared` (`artist`, `you`, `partner`), `only_you` and `only_partner` (`artist`, `count`). `overlap` is the sum over all artists of the smaller of the two listen shares, from 0 (no artist in common) to 1 (the same mix), and `null` while one side has no listens. 404 for anyone outside the pair. |
| `DELETE` | `/comparisons/{id}` | Ends the pair, from either side. |

### Spellings (session-gated)

Last.fm sometimes reports one artist in several spellings. A user can merge
them into one name. A merge rewrites `listens.artist` to that name and keeps
the original in `listens.artist_raw`, so every query follows without a
change and undoing a merge restores the spelling. The poller and imports
apply merges to new listens. Covers, tags, release years and durations that
the variants already have are copied to the merged name.

| Method | Path | Description |
|---|---|---|
| `GET` | `/merges` | `{"suggestions": [{"names": [{"artist", "listens"}], "listens"}], "merges": [{"canonical", "listens", "variants": [{"artist", "listens"}]}]}`. Suggestions group the user's artists by a key that ignores case, accents, a leading "the", "&" against "and", punctuation, whitespace and a "feat." part. Nothing is merged without a request. |
| `POST` | `/merges` | Merges `{"canonical": "...", "variants": ["..."]}` and returns the same as `GET`. Variants that are canonical names of other merges take their own variants along. 422 for an empty name, no other spelling, or a canonical name that is itself merged into another. |
| `DELETE` | `/merges?canonical=...&variant=...` | Splits one variant off again, or every variant without `variant`. 404 when there is no such merge. |

### Imports (session-gated)

| Method | Path | Description |
|---|---|---|
| `POST` | `/imports?filename=...` | The file is the raw request body: Spotify's Extended streaming history (`Streaming_History_Audio_*.json`, or the zip Spotify sends, whose video history is left out) or a ListenBrainz export (the zip with `listens/<year>/<month>.jsonl`, one JSONL file, or a JSON array). Answers 202 with the import, which runs in the background. 413 above `TIDALWAVE_IMPORT_MAX_BYTES`, 422 for an empty body, 409 while another import of the user is pending or running. |
| `GET` | `/imports` | The user's imports, newest first: `id`, `filename`, `source`, `status` (`pending`, `running`, `done`, `failed`, `undone`), `error`, the counts `read`, `skipped`, `too_short`, `duplicates`, `added`, the span `first_played_at`/`last_played_at` of the added listens, and timestamps. An import that has not updated for ten minutes is marked failed. |
| `GET` | `/imports/{id}` | One import, for polling. |
| `DELETE` | `/imports/{id}` | Undoes an import: deletes the listens it added and marks it `undone`. 409 while it runs. |

A play counts when Last.fm would have scrobbled it: at least 30 seconds, and
half the track or four minutes when its length is known (from ListenBrainz,
or from the durations cache for Spotify). Spotify's `ts` is the end of a play,
so it is stored as `ts` minus `ms_played`. Podcasts, entries without a track
name and private sessions are skipped. A play of the same artist and track
within ten minutes of a listen the user already has counts as a duplicate;
each existing listen absorbs one play at most, and importing a file again
adds nothing. `listens.source` is `lastfm`, `spotify` or `listenbrainz`.

### Shares (session-gated)

| Method | Path | Description |
|---|---|---|
| `POST` | `/shares` | Creates a share link. Optional JSON body: `label`, and a range as `range_from`/`range_to` (instants), `start`/`end` (local dates) or `range_key`. Without a range the share covers all time. |
| `GET` | `/shares` | Lists the user's active shares, newest first. |
| `DELETE` | `/shares/{token}` | Revokes a share owned by the authenticated user. |

### Public shared views (no auth required)

Every `/stats/...` endpoint above also exists as `/shared/{token}/...` and
returns the share owner's data, limited to the share's range. Range parameters
can narrow that range and never widen it. A revoked or unknown token is a 404.
`previous` in the summary is always `null` here, because the period before
lies outside the share. `/shared/{token}/now-playing` always returns `null`
for the same reason and never asks Last.fm.

A share created with `range_key` (`rolling_7d`, `rolling_30d`, `rolling_365d`,
`this_week`, `this_month`, `this_year`) stores the symbol instead of two
instants. Its range is resolved in the owner's timezone on every request, so
the link keeps showing the last 30 days or the current month.

Responses under `/shared/` carry `Access-Control-Allow-Origin: *`, so a page
on another origin can read a share. No other route sends CORS headers.

### Share pages (no auth required)

| Method | Path | Description |
|---|---|---|
| `GET` | `/s/{token}` and every path below it | The frontend's `index.html` with Open Graph tags for the share added to its head: the owner's name and the share's label as title, the range, listen count and top artist as description, and an album cover from the range as image. All of it is computed inside the share's range. The shell is fetched from `TIDALWAVE_FRONTEND_URL` and cached for a minute. A revoked or unknown token gets the unchanged shell with status 404. |

---

## Running the poller and backfill

These are console scripts installed by `uv sync` (see `[project.scripts]` in `pyproject.toml`).

**One-pass poll** — fetches new scrobbles for every connected user since their last sync:

```bash
tidalwave-poll
```

This is intended to be run on a schedule, e.g. every 5 minutes via cron or a Kubernetes CronJob.
Per-user failures are isolated (one bad account never aborts the run). If a user's Last.fm
session key is invalid/revoked (auth error), that user is flagged `disconnected` and skipped on
subsequent polls until they reconnect via `/auth/login`; transient errors (rate limits, outages)
are logged and retried on the next run. A user who deletes their account while a run is in
progress is reported as `gone` and skipped.

Reads are authenticated with each user's stored Last.fm session key, so private "hide recent
listening" profiles are readable; public profiles work either way.

**Full-history backfill** — imports a user's entire Last.fm history (may take a while for accounts with many scrobbles):

```bash
tidalwave-backfill <lastfm-username>
```

**Album covers** — the poll stores cover URLs it sees and looks up to 50 missing albums per run; this fills the rest of the history:

```bash
tidalwave-backfill-covers
```

**Genre tags**: the poll asks Last.fm for the tags of up to 50 artists per run (`artist.getTopTags`) and keeps the ones that describe the music. This fetches the tags for every artist that has none yet:

```bash
tidalwave-backfill-tags
```

**Release years**: the poll looks up the release year of up to `TIDALWAVE_MUSICBRAINZ_BUDGET` albums per run on MusicBrainz, using the album and track ids Last.fm sends with a scrobble. Albums whose scrobbles carry neither id stay without a year. This works through every album that has not been asked for yet, at one request per second:

```bash
tidalwave-backfill-years
```

**Weekly report**: posts one Discord embed per user with a saved webhook. It covers the last full ISO week (Monday to Sunday) in the user's timezone: listening time and listens with the change against the week before, the top artist, the top track and the artists first heard that week. A week without listens sends nothing. A failing webhook is logged and the run goes on with the next user; the command exits 0 either way. The message links to `TIDALWAVE_PUBLIC_BASE_URL`.

```bash
tidalwave-weekly-report
```

The week is the one that has ended in each user's timezone when the command runs. Run on Monday at 08:00 in Berlin, that is the week just past nearly everywhere, but in Los Angeles and further west it is still Sunday, so those users get the week before. There is no report by mail, since tidalwave has no SMTP configuration.

All commands read configuration from the same `TIDALWAVE_*` environment variables as the server.

---

## Tests

Tests require a running PostgreSQL instance. By default the test suite connects to the same URL as the application default (`postgresql+asyncpg://tidalwave:tidalwave@localhost:5432/tidalwave`). Override with:

```bash
export TIDALWAVE_TEST_DATABASE_URL=postgresql+asyncpg://...
```

Run the suite:

```bash
uv run pytest
```
