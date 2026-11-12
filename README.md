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
  time, the listening clock, weekdays, top lists and recent listens.
- A page for every artist, album and track, with album covers and search
  links to Spotify, Tidal, Apple Music, YouTube Music and Deezer.
- Insights: on this day, streaks and records, milestones, a listening
  heatmap, a weekday by hour grid and discoveries.
- Rolling, calendar and custom ranges, resolved in each user's timezone.
- Search across artists, albums and tracks from the header (`/` or Ctrl+K).
- Read-only share links, optionally limited to a range and revocable from a
  list.

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

Last.fm is the only external dependency. There is no Redis — stats are queried
directly from Postgres.

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
The Ingress routes `/auth`, `/stats`, `/shares`, and `/shared` to the backend
and everything else to the frontend.

**Poller** runs as a Kubernetes CronJob (`*/5 * * * *` by default). Adjust the
schedule with `--set poller.schedule='*/10 * * * *'` or disable with
`--set poller.enabled=false`.

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
