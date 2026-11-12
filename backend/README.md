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
| `TIDALWAVE_REGISTRATION_ALLOWLIST` | *(empty)* | Comma-separated list of Last.fm usernames permitted to register when `REGISTRATION_MODE=allowlist`. Example: `alice,bob`. |
| `TIDALWAVE_SESSION_SECRET` | `dev-insecure-change-me` | Secret used to sign the session cookie with itsdangerous. **Must be set to a strong random value in production.** |
| `TIDALWAVE_FRONTEND_URL` | *(empty)* | Base URL the backend fetches the frontend's `index.html` from, to serve `/s/<token>` with link-preview tags. Needs the ingress to route `/s/` to the backend. Empty: `/s/<token>` on the backend answers with a small page that carries the tags and forwards to `/?share=<token>`. |
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
| `GET` | `/auth/me` | Session | Username, admin flag, timezone, `disconnected`, `last_synced_at` and `last_played_at`. |
| `PATCH` | `/auth/me` | Session | Sets the timezone: `{"timezone": "<IANA name>"}`, 422 for an unknown name. |
| `DELETE` | `/auth/me` | Session | Deletes the user with their listens, shares and sync state, and clears the session cookie. The shared `album_art` and `track_durations` caches stay. |
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
| `GET` | `/stats/discoveries` | `limit` | New artists, new tracks and rediscoveries in the range. |
| `GET` | `/stats/genres` | `limit` | Genres ranked by the listens of their artists: `{"genres": [{"genre", "listens", "artists"}], "artists": N, "tagged_artists": M}`. An artist's listens count in full for each of its first three tags. `artists` is the number of artists in the range and `tagged_artists` how many of them have been looked up on Last.fm, so a client can tell when the ranking is still filling in. |
| `GET` | `/stats/genre` | `genre` | Totals for one genre in the range: listens, seconds and artists. 404 when no artist the user has listened to carries the tag among its first three. |
| `GET` | `/stats/records` | | Longest and current streak, busiest day, longest session. |
| `GET` | `/stats/heatmap` | | Listens per day, at most 366 days. |
| `GET` | `/stats/on-this-day` | | Listens on today's date in earlier years. Ignores the range parameters. |
| `GET` | `/stats/now-playing` | | The track Last.fm reports as playing right now (`track`, `artist`, `album`, `image_url`), or `null`. Takes no range. The answer is kept in memory for 15 seconds per user, and a Last.fm failure yields `null`. |
| `GET` | `/stats/milestones` | | Round listen counts reached so far and the next one. Ignores the range parameters. |

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
