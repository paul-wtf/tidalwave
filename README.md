# tidalwave

**Self-hosted, multi-user listening tracker for Tidal users.** Because Tidal
exposes no listening-history API, tidalwave works through Last.fm: users connect
their Last.fm account (which they already use to scrobble from the Tidal app),
and tidalwave polls `user.getRecentTracks` on a schedule to ingest their history
into Postgres. A FastAPI backend aggregates the data into per-user stats and
a SvelteKit dashboard shows them. Access is gated and multi-user from day one:
each user sees only their own data. See the
[design spec](docs/superpowers/specs/2026-06-17-tidalwave-listening-tracker-design.md)
for full background and the
[stats extensions spec](docs/superpowers/specs/2026-11-06-stats-extensions-design.md)
for the detail pages and Insights.

## Features

- Overview with totals, their change against the previous period, trends over
  time, the listening clock, weekdays, top lists, recent listens and the
  track that is playing right now.
- A page for every artist, album and track, with album covers and search
  links to Spotify, Tidal, Apple Music, YouTube Music and Deezer. With a
  [linkhop](https://github.com/paul-wtf/linkhop) instance configured, one
  more link finds the item on every service at once.
- Insights: on this day, streaks and records, milestones, a listening
  heatmap, a weekday by hour grid, genres, listens by release decade,
  albums played through and discoveries.
- Genres from Last.fm's artist tags, with a page per genre, and release
  years from MusicBrainz. Both are fetched a few at a time with every
  poll.
- A race of the top ten artists on the Artists page, stepping through the
  selected range.
- Rolling, calendar and custom ranges, resolved in each user's timezone.
- Search across artists, albums and tracks from the header (`/` or Ctrl+K).
- A cover collage of the top albums of a range (3×3, 4×4 or 5×5) as a PNG
  download.
- Export of all your listens as CSV or JSON, and account deletion, from the
  user menu.
- Read-only share links, revocable from a list. A link covers all time, a
  fixed range, or a range that keeps moving, such as the last 30 days.
- Link previews for share links: a chat app shows whose listening it is,
  the range, the listen count, the top artist and a cover.
- Comparisons between two users who both agreed: one sends an invite
  link, the other accepts, and both see how much their listening
  overlaps in a range, the artists they share and the ones only one of
  them played. Either side can end it.
- A weekly report to Discord: each user can save a webhook and gets
  last week's listening, top artist, top track and new artists every
  Monday.
- An admin page that lists the accounts, deletes one with all its data,
  and adds names to the allowlist at runtime.

## Architecture

```
Tidal app ──scrobbles──► Last.fm ◄──polls──  poller (CronJob)
                                                   │ upsert
                                                   ▼
                                           Postgres (listens)
                                                   │ aggregates
                                                   ▼
                                       FastAPI /stats  ◄──  SvelteKit
```

Last.fm is the only external dependency the app needs. The poller also asks
MusicBrainz for album release years, which can be turned off. There is no
Redis — stats are queried directly from Postgres.

## Stack

| Layer      | Tech                                                              |
| ---------- | ----------------------------------------------------------------- |
| Backend    | Python 3.12 (uv), FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic |
| Frontend   | SvelteKit (`adapter-static`), TypeScript, Vite                    |
| Database   | Postgres 16 (CNPG in production)                                  |
| Tests      | pytest, Playwright (E2E), Vitest (components)                     |
| Packaging  | Docker images, Helm chart                                         |
| Deployment | FluxCD → RKE2 + Traefik + cert-manager + external-dns             |

## Local development

### Backend

Requires [uv](https://docs.astral.sh/uv/) and a running PostgreSQL instance
(`docker-compose up -d` starts one on `localhost:5432`):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn tidalwave.main:app --port 8080
```

The API is available at `http://localhost:8080`.

See [`backend/README.md`](backend/README.md) for the full environment-variable
reference, Last.fm connect flow, and poller/backfill scripts.

### Frontend

Requires Node 24+ and [pnpm](https://pnpm.io/):

```bash
cd frontend
pnpm install
pnpm gen:api          # generate typed client from backend/openapi.json
pnpm dev              # http://localhost:5173
```

## Deployment

The Helm chart is in [`helm/tidalwave/`](helm/tidalwave/).

```bash
helm install tidalwave helm/tidalwave \
  --namespace tidalwave --create-namespace \
  --set config.publicBaseUrl=https://tidalwave.example.com \
  --set secrets.databaseUrl='postgresql+asyncpg://user:pass@host:5432/tidalwave' \
  --set secrets.lastfmApiKey=<key> \
  --set secrets.lastfmApiSecret=<secret> \
  --set secrets.sessionSecret=<random-string> \
  --set ingress.host=tidalwave.example.com
```

Required values:

| Value | Description |
| --- | --- |
| `config.publicBaseUrl` | Public HTTPS URL; used to build the Last.fm OAuth callback. |
| `secrets.databaseUrl` | Async SQLAlchemy URL (`postgresql+asyncpg://...`). |
| `secrets.lastfmApiKey` | Last.fm API key (obtain at last.fm/api/account/create). |
| `secrets.lastfmApiSecret` | Last.fm API secret. |
| `secrets.sessionSecret` | Strong random secret for signing session cookies. |
| `ingress.host` | Hostname for the Ingress rule. |

**Postgres** is external (CNPG-managed); the chart does not deploy a database.
The Ingress routes `/auth`, `/stats`, `/shares`, `/shared`, `/comparisons`,
`/merges` and `/imports` to the backend and everything else to the frontend.

**Link previews** are on by default (`config.sharePreviews`). The Ingress then
also routes `/s/` to the backend, which serves share pages as the frontend's
`index.html` plus Open Graph tags and fetches that file from the frontend
Service inside the cluster. With `--set config.sharePreviews=false` share
pages come straight from the frontend and carry no preview.

**Poller** runs as a Kubernetes CronJob (`*/5 * * * *` by default). Adjust the
schedule with `--set poller.schedule='*/10 * * * *'` or disable with
`--set poller.enabled=false`. Each run also looks up the release year of up
to `poller.releaseYearBudget` albums on MusicBrainz (30 by default, one
request per second), so the poller needs to reach `musicbrainz.org` as well
as Last.fm. `--set poller.releaseYearBudget=0` turns that off, and
`poller.musicbrainzUrl` points it at a mirror.

**Weekly report** is off by default. `--set weeklyReport.enabled=true` adds a
CronJob that runs `tidalwave-weekly-report` on the backend image every Monday
at 08:00 Europe/Berlin (`weeklyReport.schedule`, `weeklyReport.timeZone`; the
`timeZone` field needs Kubernetes 1.27). It posts to the Discord webhooks
users saved, so the job needs to reach `discord.com` and `discordapp.com`,
and so does the backend, which sends the test message from the user menu.
Users in Los Angeles and further west get the week before last, because
their week has not ended yet when the job runs. There is no report by mail:
tidalwave has no SMTP configuration.

**Registration** follows `config.registrationMode`. In `allowlist` mode the
names in `config.registrationAllowlist` may sign up, plus the names an admin
adds on the admin page, which live in the database. The first account is the
admin.

**Imports** of older history accept uploads up to `config.importMaxMegabytes`
(100 MB by default). The chart sets `nginx.ingress.kubernetes.io/proxy-body-size`
on the Ingress to the same size unless `ingress.annotations` sets it already;
with another ingress controller, raise its body limit there. An upload waits
in the backend container's temp directory while it is imported, and needs no
outbound access.

**linkhop** is optional: `--set config.linkhopUrl=https://linkhop.example`
adds a link to every item that opens it as a search on that
[linkhop](https://github.com/paul-wtf/linkhop) instance.

Alternatively, supply credentials via an existing Secret and skip chart-managed
secret creation:

```bash
--set secrets.existingSecret=my-tidalwave-secret
```

The Secret must contain: `TIDALWAVE_DATABASE_URL`, `TIDALWAVE_LASTFM_API_KEY`,
`TIDALWAVE_LASTFM_API_SECRET`, `TIDALWAVE_SESSION_SECRET`.

## CI / CD

GitHub Actions workflows in [`.github/workflows/`](.github/workflows/) run on
[github.com/paul-wtf/tidalwave](https://github.com/paul-wtf/tidalwave). Pull
requests get the backend and frontend checks. Publishing a GitHub release
builds both images and pushes them to GHCR as
`ghcr.io/paul-wtf/tidalwave-backend` and `ghcr.io/paul-wtf/tidalwave-frontend`,
tagged with the release version and `latest`. A push to `master` that touches
`helm/` releases the chart through `helm/chart-releaser-action` into the Helm
repository at `https://paul-wtf.github.io/tidalwave`.
