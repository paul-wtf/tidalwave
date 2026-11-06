# Stats extensions implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix album identity and timezone handling, and add share management, sync status, calendar ranges, period comparison, detail pages, covers and an insights page.

**Architecture:** A single `Scope` (user, timezone, range, share clamp) is resolved by one FastAPI dependency per mode (session or share token), and one stats router is mounted under both `/stats` and `/shared/{token}`. All queries take a `Scope`. The frontend gets one `statsApi(token?)` client so every component works in both modes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic, Postgres 16; SvelteKit 2 / Svelte 5 runes, TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-06-stats-extensions-design.md`. Read it before any task; the "Edge cases" section is binding.

## Global constraints

- New endpoints live under `/auth`, `/stats`, `/shares` or `/shared` only.
- Ranges are half-open `[since, until)` instants everywhere.
- NULL `users.timezone` means `UTC`.
- Stats `limit` parameters: `Query(20, ge=1, le=500)` (default stays as today per endpoint).
- Existing `/stats/…` and `/shared/{token}/…` paths and response fields stay; changes are additive.
- No new Python or npm dependencies. `zoneinfo` is stdlib.
- Last.fm placeholder hash: `2a96cbd8b46e442fc41c2b86b821562f`.
- Thresholds: rediscovery gap 180 days, session gap 30 minutes, cover poll budget 50.
- Commits: Conventional Commits, `feat(<area>): …` / `fix(<area>): …`, areas `backend`, `frontend`, `docs`. Body wrapped at 72. No `Co-Authored-By`, no tool attribution of any kind.
- Code comments: default is none. Only where a reader cannot derive the reason from the code.
- Use CodeGraph first to find code: `codegraph explore "<symbols or question>"` from the repo root.

### Running things (machine `dev`)

The repo has no flake. Every command runs through the wrapper, which provides uv, Python 3.12, Node 24 and pnpm and sets `LD_LIBRARY_PATH` for greenlet:

    W=/tmp/claude-1000/-home-paul-git/0cf25304-2d1b-5053-9ca2-26b23ec8c728/scratchpad/twenv.sh

- Postgres runs in podman as `tw-pg` on `localhost:5432` (`tidalwave`/`tidalwave`). Start it if `podman ps` doesn't list it: `podman start tw-pg`.
- Backend: `cd backend && $W uv run pytest -q -p no:cacheprovider`, `$W uv run ruff check src tests`, `$W uv run mypy src`.
- Frontend: `cd frontend && $W pnpm test`, `$W pnpm check`, `$W pnpm build`.
- `dev` has 2 CPUs: never run backend and frontend suites in parallel.

## Review focus

1. Names with `&`, `/`, `#`, `?`, `+`, quotes and non-ASCII in artist/album/track: detail links must round-trip exactly. Tests in Task 9 (backend) and Task 17 (`links.ts`).
2. Share leakage: first/last listen, discoveries' "first ever", rediscoveries' previous listen and on-this-day must never see listens outside the share range. Tests in Tasks 10 and 11.
3. DST: `this_month` for Europe/Berlin across the 2026-10-25 change resolves to local midnights (`2026-10-01T00:00+02:00`, `2026-11-01T00:00+01:00`). Test in Task 2.
4. A user with zero listens: every new endpoint returns empty lists or nulls with 200, detail endpoints 404. Tests in Tasks 9 to 11.
5. Calendar compare at month end: `start=2026-03-31` shifted by one month is `2026-02-28`. Test in Task 6.

---

## Backend

### Task 1: Schema and migration

**Files:**
- Modify: `backend/src/tidalwave/models/db.py`
- Create: `backend/migrations/versions/<rev>_stats_extensions.py` (down_revision `a1d2e3f40510`)
- Test: `backend/tests/models/test_db_models.py`

**Interfaces:**
- Produces: `User.timezone: Mapped[str | None]` (`String(64)`), `Share.label: Mapped[str | None]` (`Text`), model `AlbumArt` (`album_art`: `id`, `artist` Text, `album` Text, `image_url` Text nullable, `fetched_at` timestamptz server default now, `UniqueConstraint("artist", "album", name="uq_album_art")`), index `ix_listens_user_artist_played` on `listens (user_id, artist, played_at)`.

- [ ] Write `test_album_art_unique_per_artist_album` (two rows same `(artist, album)` raise `IntegrityError`; same album, other artist is fine) and `test_user_timezone_defaults_to_null`.
- [ ] Run them, expect FAIL (no `AlbumArt`).
- [ ] Add the columns, model and index (`Index` in `Listen.__table_args__`); write the migration by hand mirroring `a1d2e3f40510_track_durations.py`, with a working `downgrade`.
- [ ] Run the model tests, then `cd backend && $W uv run alembic upgrade head && $W uv run alembic downgrade -1 && $W uv run alembic upgrade head` against `tw-pg`. Expect no errors.
- [ ] Commit `feat(backend): add timezone, share labels and album art tables`.

### Task 2: Scope, range resolution, unified stats router, timezone in queries

**Files:**
- Create: `backend/src/tidalwave/stats/scope.py`
- Modify: `backend/src/tidalwave/stats/queries.py`, `backend/src/tidalwave/routes/stats.py`, `backend/src/tidalwave/routes/share.py`, `backend/src/tidalwave/main.py`
- Test: `backend/tests/stats/test_scope.py` (new), `backend/tests/stats/test_queries.py`, `backend/tests/routes/test_stats_routes.py`, `backend/tests/routes/test_share_routes.py`

**Interfaces:**
- Produces in `stats/scope.py`:
  - `@dataclass(frozen=True, slots=True) class Scope: user_id: int; tz: str; since: datetime | None; until: datetime | None; floor: datetime | None = None; ceiling: datetime | None = None; shared: bool = False`: `floor`/`ceiling` are the share's range (None for own views); `since`/`until` are already intersected with them.
  - `def resolve_range(tz: str, *, since: datetime | None, until: datetime | None, start: date | None, end: date | None) -> tuple[datetime | None, datetime | None]`: `start`/`end` (local dates, `end` exclusive) become local midnights in `tz` as aware datetimes; they win over `since`/`until` when given. 422 (`HTTPException`) if both forms are mixed.
  - `def intersect(since, until, floor, ceiling) -> tuple[datetime | None, datetime | None]`: max of lower bounds, min of upper bounds.
  - `def user_tz(user: User) -> str`: `user.timezone or "UTC"`.
  - `async def own_scope(user=Depends(current_user), since: datetime | None = None, until: datetime | None = None, start: date | None = None, end: date | None = None) -> Scope`
  - `async def shared_scope(token: str, since…, until…, start…, end…, session=Depends(get_session)) -> Scope`: resolves the non-revoked share (404 otherwise), loads its owner for `tz`, sets `floor`/`ceiling` from the share, `shared=True`.
- Produces in `routes/stats.py`: `def make_stats_router(scope_dep) -> APIRouter`; `main.py` includes it with `prefix="/stats"` (`own_scope`) and `prefix="/shared/{token}"` (`shared_scope`). Paths stay `top-artists`, `top-tracks`, `top-albums`, `clock`, `weekday`, `history`, `metrics-over-time`, `recent`, `summary`.
- Produces in `queries.py`: every function takes `(session, scope: Scope, *, …)` instead of `(session, user_id, *, since, until)`; `_scope(stmt, scope)` applies user and range; every `func.timezone("UTC", …)` becomes `func.timezone(scope.tz, …)`.
- `routes/share.py` keeps only `POST /shares`, `DELETE /shares/{token}`; the `/shared/…` handlers are deleted.

- [ ] Write `test_scope.py`:
  - `test_resolve_range_local_midnights_across_dst`: `resolve_range("Europe/Berlin", since=None, until=None, start=date(2026,10,1), end=date(2026,11,1))` == `(datetime(2026,9,30,22,tzinfo=UTC), datetime(2026,10,31,23,tzinfo=UTC))`.
  - `test_resolve_range_passes_instants_through`, `test_resolve_range_rejects_mixed_forms` (422).
  - `test_intersect_never_widens`: floor `2026-01-01`, ceiling `2026-02-01`, request `2025-06-01..2027-01-01` gives `2026-01-01..2026-02-01`; request `None..None` gives the floor and ceiling.
- [ ] Add route tests: `test_clock_uses_user_timezone` (user tz `Europe/Berlin`, listen at `2026-07-01T10:00Z`, `/stats/clock` has `1` at index 12), `test_shared_view_cannot_widen_share_range` (share with range Jan 2026, listens in Dec 2025 and Jan 2026, `/shared/{t}/summary?since=2025-01-01T00:00:00Z` counts 1), `test_limit_capped_at_500` (`limit=501` gives 422), `test_shared_paths_unchanged` (all nine `/shared/{t}/…` paths return 200).
- [ ] Run, expect FAIL.
- [ ] Implement `scope.py`, refactor queries and routes as above; update existing query tests to build a `Scope(user_id=…, tz="UTC", since=…, until=…)`.
- [ ] Run the full backend suite, ruff and mypy. Expect all green.
- [ ] Commit `feat(backend): resolve stats scope once and serve own and shared views from one router` (body: why the twin routes went, and that queries are now timezone-aware).

### Task 3: Album identity

**Files:**
- Modify: `backend/src/tidalwave/stats/queries.py`
- Test: `backend/tests/stats/test_queries.py`

**Interfaces:**
- Produces: `top_albums` rows `{"album": str | None, "artist": str, "count": int}`, grouped by `(artist, album)`, ordered `count desc, album asc, artist asc`. `distinct_albums` (summary) and `albums` (metrics) count distinct `(artist, album)` pairs where `album IS NOT NULL`.

- [ ] Write `test_top_albums_split_same_name_by_artist` ("Greatest Hits" by A ×2 and by B ×1 give two rows with counts 2 and 1 and their artists), `test_distinct_albums_counts_artist_album_pairs` (summary `distinct_albums == 2` for the same data; a NULL-album listen adds nothing), `test_unknown_album_rows_split_by_artist`.
- [ ] Run, expect FAIL.
- [ ] Implement with the existing `_top(..., extra=(Listen.artist, "artist"))` and `func.count(distinct(tuple_(Listen.artist, Listen.album)))` filtered on `Listen.album.is_not(None)` (use `FILTER`/`CASE`, keep one query).
- [ ] Run backend suite. Expect green.
- [ ] Commit `fix(backend): treat an album as artist plus title`.

### Task 4: Account info, timezone setting, sync timestamp

**Files:**
- Modify: `backend/src/tidalwave/routes/auth.py`, `backend/src/tidalwave/ingest/repository.py`, `backend/src/tidalwave/ingest/service.py`
- Test: `backend/tests/routes/test_auth_routes.py`, `backend/tests/ingest/test_service.py`

**Interfaces:**
- Produces: `GET /auth/me` → `{"username", "is_admin", "timezone": str | None, "disconnected": bool, "last_synced_at": str | None, "last_played_at": str | None}` (ISO strings). `PATCH /auth/me` with body model `MeUpdate(timezone: str)` → same shape; 422 when `ZoneInfo(timezone)` raises.
- Produces: `async def mark_synced(session, user_id: int) -> None` in `repository.py`: upserts `sync_state` setting `last_synced_at = now()` and leaving `last_played_at` untouched. `_collect_and_store` calls it after every successful run, also when nothing new arrived.

- [ ] Write `test_me_includes_sync_and_timezone`, `test_patch_me_sets_timezone` (`Europe/Berlin` → 200 and persisted), `test_patch_me_rejects_unknown_timezone` (`Mars/Olympus` → 422), `test_ingest_without_new_scrobbles_still_marks_synced` (fake source returns an empty page; `sync_state.last_synced_at` is set, `last_played_at` stays None).
- [ ] Run, expect FAIL.
- [ ] Implement.
- [ ] Run backend suite. Expect green.
- [ ] Commit `feat(backend): expose sync state and let users set their timezone`.

### Task 5: Share management

**Files:**
- Modify: `backend/src/tidalwave/routes/share.py`
- Test: `backend/tests/routes/test_share_routes.py`

**Interfaces:**
- Produces: `POST /shares` with optional body `ShareCreate(label: str | None = None, range_from: datetime | None = None, range_to: datetime | None = None, start: date | None = None, end: date | None = None)`. `start`/`end` are local dates resolved with `resolve_range` in the owner's timezone; `start` without `end` freezes the end at now. Mixing both forms gives 422, as does `range_from >= range_to` after resolution. Response `{"share_token", "label", "range_from", "range_to", "created_at"}` (201).
- Produces: `GET /shares` → list of the same shape for the user's non-revoked shares, newest first.

- [ ] Write `test_create_share_with_label_and_range`, `test_create_share_from_local_dates_uses_owner_timezone` (Berlin, `start=2026-10-01`, `end=2026-11-01` → `2026-09-30T22:00Z`..`2026-10-31T23:00Z`), `test_create_share_without_body_still_works` (existing behaviour), `test_list_shares_excludes_revoked_and_other_users`, `test_create_share_rejects_inverted_range`.
- [ ] Run, expect FAIL. Implement. Run backend suite, expect green.
- [ ] Commit `feat(backend): list shares and create them with a label and range`.

### Task 6: Previous-period comparison

**Files:**
- Modify: `backend/src/tidalwave/stats/scope.py`, `backend/src/tidalwave/routes/stats.py`
- Test: `backend/tests/stats/test_scope.py`, `backend/tests/routes/test_stats_routes.py`

**Interfaces:**
- Produces: `def previous_range(tz: str, since: datetime, until: datetime | None, calendar: Literal["week", "month", "year"] | None, now: datetime) -> tuple[datetime, datetime]`: `until=None` means `now`. With `calendar`, both bounds move back one unit in local time (week = 7 days; month/year clamp the day to the target month's length). Without, the window of equal length right before `since`.
- Produces: `GET …/summary?compare=true&calendar=<unit>` adds `"previous": Summary | None`. `previous` is None when `since` is None (all time) or `scope.shared`.

- [ ] Write `test_previous_range_rolling`, `test_previous_range_this_month_same_elapsed_span` (Berlin, since Nov 1 local, until None, now 2026-11-06T12:00Z → Oct 1 local … 2026-10-06T12:00Z), `test_previous_range_completed_month` (Oct 1..Nov 1 → Sep 1..Oct 1), `test_previous_range_clamps_month_end` (since 2026-03-31 local, calendar month → 2026-02-28 local), `test_summary_compare_omitted_for_all_time_and_shares`.
- [ ] Run, expect FAIL. Implement. Run backend suite, expect green.
- [ ] Commit `feat(backend): compare a range's summary with the previous period`.

### Task 7: Cover ingest

**Files:**
- Modify: `backend/src/tidalwave/lastfm/client.py`, `backend/src/tidalwave/models/domain.py`, `backend/src/tidalwave/ingest/repository.py`, `backend/src/tidalwave/ingest/service.py`, `backend/src/tidalwave/cli.py`, `backend/pyproject.toml`, `backend/README.md`
- Create: `backend/src/tidalwave/ingest/covers.py`
- Test: `backend/tests/lastfm/test_client_recent.py`, `backend/tests/ingest/test_covers.py` (new), `backend/tests/ingest/test_repository.py`, `backend/tests/test_cli.py`

**Interfaces:**
- Produces: `Scrobble.image_url: str | None = None`; `_parse_track` takes the `extralarge` entry of `t["image"]`, empty or placeholder-hash URLs become None.
- Produces: `LastfmClient.get_album_info(artist: str, album: str) -> str | None` (unsigned `album.getInfo`, same image rule; Last.fm error 6 "not found" returns None).
- Produces: `async def upsert_album_art(session, scrobbles: Sequence[Scrobble]) -> None` in `repository.py`; skips `album is None`; on conflict sets `image_url = coalesce(excluded.image_url, album_art.image_url)`, `fetched_at = now()`. Called from `_collect_and_store`.
- Produces in `covers.py`: `class AlbumInfoSource(Protocol)` and `async def fill_missing_covers(session, client, *, max_albums: int | None = None) -> int`: distinct `(artist, album)` from `listens` with no `album_art` row, fetched one by one, a row written even when None; returns rows written. Mirrors `durations.py`, including its handling of transient errors.
- Produces: CLI `tidalwave-backfill-covers` (`tidalwave.cli:backfill_covers`), and `_POLL_COVER_BUDGET = 50` used in `_poll`.

- [ ] Write `test_parse_track_keeps_extralarge_image`, `test_parse_track_drops_placeholder_image`, `test_upsert_album_art_url_wins_over_null`, `test_upsert_album_art_newer_url_replaces_older`, `test_fill_missing_covers_writes_null_rows_and_respects_budget`, `test_backfill_covers_cli_registered`.
- [ ] Run, expect FAIL. Implement; add the script to `pyproject.toml` and a line to `backend/README.md` next to `tidalwave-backfill-durations`. Run backend suite, expect green.
- [ ] Commit `feat(backend): store album covers from Last.fm`.

### Task 8: Covers in stats responses

**Files:**
- Modify: `backend/src/tidalwave/stats/queries.py`
- Test: `backend/tests/stats/test_queries.py`

**Interfaces:**
- Produces: `image_url: str | None` on `top_albums` rows (join `album_art` on artist+album), `top_artists` rows (cover of the artist's most-listened album within the scope; ties by album name), `recent_listens` rows.

- [ ] Write `test_top_albums_carry_cover`, `test_top_artist_cover_is_most_listened_album_in_scope` (album X most listened overall, album Y most listened inside the range → range query returns Y's cover), `test_recent_listens_carry_cover`, `test_missing_cover_is_null`.
- [ ] Run, expect FAIL. Implement. Run backend suite, expect green.
- [ ] Commit `feat(backend): return covers with top lists and recent listens`.

### Task 9: Detail endpoints and entity filters

**Files:**
- Create: `backend/src/tidalwave/stats/details.py`
- Modify: `backend/src/tidalwave/stats/queries.py`, `backend/src/tidalwave/routes/stats.py`
- Test: `backend/tests/stats/test_details.py` (new), `backend/tests/routes/test_stats_routes.py`

**Interfaces:**
- Produces: optional `artist: str | None`, `album: str | None`, `track: str | None` filters on `top_tracks`, `top_albums`, `metrics_over_time`, `recent_listens` (query params of the same names on their routes). Exact match.
- Produces in `details.py`:
  - `artist_detail(session, scope, artist) -> dict | None` → `{"artist", "listens", "seconds", "rank": int | None, "first_listen", "last_listen", "image_url"}`
  - `album_detail(session, scope, artist, album) -> dict | None` → `{"artist", "album", "listens", "seconds", "first_listen", "last_listen", "image_url"}`
  - `track_detail(session, scope, artist, track) -> dict | None` → `{"artist", "track", "album": str | None, "listens", "seconds", "first_listen", "last_listen", "image_url"}` (album = most-listened album of the track in scope, falling back to all time)
  - `listens`/`seconds`/`rank` use `since`/`until`; first/last listen use only `floor`/`ceiling`; None when the entity has no listens within `floor`/`ceiling`. `rank` is the 1-based position under the top-list ordering, None when zero listens in range.
- Produces routes: `GET …/artist?artist=`, `GET …/album?artist=&album=`, `GET …/track?artist=&track=`; 404 on None.

- [ ] Write `test_artist_detail_counts_range_but_first_listen_all_time`, `test_artist_detail_rank_matches_top_list`, `test_artist_with_listens_only_outside_range_has_zero_counts`, `test_detail_404_for_unknown_entity`, `test_detail_first_listen_clamped_to_share`, `test_detail_roundtrips_special_characters` (artist `AC/DC & "Friends" #1 ?+ Ünïcode` through the route with httpx `params=`), `test_top_tracks_filtered_by_artist`, `test_track_detail_album_is_most_listened`.
- [ ] Run, expect FAIL. Implement. Run backend suite, expect green.
- [ ] Commit `feat(backend): add artist, album and track detail endpoints`.

### Task 10: Discoveries and on this day

**Files:**
- Create: `backend/src/tidalwave/stats/insights.py`
- Modify: `backend/src/tidalwave/routes/stats.py`
- Test: `backend/tests/stats/test_insights.py` (new)

**Interfaces:**
- Produces: `discoveries(session, scope, *, limit: int = 20) -> dict` → `{"new_artists": [{"artist", "first_listen", "listens", "image_url"}], "new_tracks_count": int, "new_tracks": [{"track", "artist", "first_listen", "listens"}], "rediscoveries": [{"artist", "previous_listen", "gap_days", "listens"}]}`. All lists empty when `scope.since` is None. "First ever" and "previous listen" look back no further than `scope.floor`. Rediscovery gap ≥ 180 days.
- Produces: `on_this_day(session, scope, *, now: datetime | None = None) -> list[dict]` → newest year first, `[{"year", "listens", "top_tracks": [{"track", "artist", "count"}]}]` (top 3). Today's month/day in `scope.tz`; ignores `since`/`until`; respects `floor`/`ceiling`. 29 February is only matched in leap years.
- Produces routes `GET …/discoveries?limit=`, `GET …/on-this-day`.

- [ ] Write `test_new_artists_first_listen_inside_range`, `test_discoveries_empty_for_all_time`, `test_rediscovery_requires_180_day_gap` (179 days: not listed; 180: listed), `test_share_floor_hides_earlier_listens_from_discoveries`, `test_on_this_day_groups_previous_years_in_user_tz` (Berlin, a listen at `2025-11-05T23:30Z` counts for 6 November), `test_on_this_day_respects_share_range`, `test_insights_empty_user_returns_empty`.
- [ ] Run, expect FAIL. Implement. Run backend suite, expect green.
- [ ] Commit `feat(backend): add discoveries and on-this-day stats`.

### Task 11: Records and heatmap

**Files:**
- Modify: `backend/src/tidalwave/stats/insights.py`, `backend/src/tidalwave/routes/stats.py`
- Test: `backend/tests/stats/test_insights.py`

**Interfaces:**
- Produces: `records(session, scope, *, now: datetime | None = None) -> dict` → `{"longest_streak": {"days", "start", "end"} | None, "current_streak": {"days", "start"} | None, "busiest_day": {"date", "listens"} | None, "longest_session": {"start", "listens", "seconds"} | None}`. Days are local dates in `scope.tz` (ISO `YYYY-MM-DD`). `current_streak` only when the range includes now; it may end yesterday. Session break: next listen more than 30 minutes after the previous one starts. Use window functions (gaps-and-islands), one query per record.
- Produces: `heatmap(session, scope, *, now: datetime | None = None) -> dict` → `{"start": date, "end": date, "days": [{"date", "listens"}]}` with only non-zero days listed; window = the range if ≤ 366 days, else the 365 days ending at the range end (`until` or now).
- Produces routes `GET …/records`, `GET …/heatmap`.

- [ ] Write `test_longest_streak`, `test_current_streak_may_end_yesterday`, `test_current_streak_absent_when_range_excludes_today`, `test_busiest_day_in_user_tz`, `test_longest_session_breaks_after_30_minutes` (gaps of 30 min continue, 31 min break), `test_heatmap_window_caps_at_365_days`, `test_records_empty_user`.
- [ ] Run, expect FAIL. Implement. Run backend suite, ruff and mypy, expect green.
- [ ] Regenerate the API schema: `cd backend && $W uv run python -c "from tidalwave.main import app; import json; json.dump(app.openapi(), open('openapi.json','w'))"` then `cd ../frontend && $W pnpm gen:api`.
- [ ] Commit `feat(backend): add streaks, records and a listening heatmap` (including `backend/openapi.json` and `frontend/src/lib/api/schema.d.ts`).

## Frontend

Every frontend task: Svelte 5 runes, existing CSS tokens (`--surface0`, `--text-muted`, `--accent-text`, `--r-sm`, …), no new dependencies. Components that take `token?: string` work in both modes.

### Task 12: One client for both modes, fetch-based test helper

**Files:**
- Modify: `frontend/src/lib/api/client.ts`, all `*.test.ts` under `frontend/src/lib/components/`, `Dashboard.svelte`, `TopPage.svelte`
- Create: `frontend/src/lib/test/mockApi.ts`

**Interfaces:**
- Produces in `client.ts`: types `Summary` (+ `previous?: Summary | null`), `ArtistCount`/`AlbumCount`/`TrackCount`/`RecentItem` with `image_url?: string | null` and `AlbumCount.artist: string`, `Me` (the Task 4 shape), `Share`, `ArtistDetail`, `AlbumDetail`, `TrackDetail`, `Discoveries`, `OnThisDayYear`, `Records`, `Heatmap`; `type StatsParams = { since?: string; until?: string; start?: string; end?: string; calendar?: 'week' | 'month' | 'year'; artist?: string; album?: string; track?: string }`.
- Produces: `function statsApi(token?: string): StatsApi` with base `/stats` or `/shared/${token}` and methods `summary(p, compare?)`, `topArtists(limit, p)`, `topTracks(limit, p)`, `topAlbums(limit, p)`, `clock(p)`, `weekday(p)`, `history(bucket, p)`, `metricsOverTime(bucket, p)`, `recent(limit, p)`, `artist(name, p)`, `album(artist, album, p)`, `track(artist, track, p)`, `discoveries(p)`, `onThisDay()`, `records(p)`, `heatmap(p)`. `api` keeps `me`, `updateMe({timezone})`, `listShares`, `createShare(body?)`, `revokeShare`, `loginUrl`, `logout`. `api.shared` is removed.
- Produces in `mockApi.ts`: `mockApi(routes: Record<string, unknown>): { calls: string[] }`: stubs `fetch` with `vi.stubGlobal`; a key matches a request path ignoring the query string; unmatched paths reject with 404.

- [ ] Rewrite the existing component tests on `mockApi`; they must keep their current assertions. Run `$W pnpm test`, expect FAIL (no `mockApi`/`statsApi`).
- [ ] Implement, switch `Dashboard` and `TopPage` to `statsApi(token)`. Use `URLSearchParams` for query strings.
- [ ] `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): serve own and shared views through one stats client`.

### Task 13: Range model and selector

**Files:**
- Modify: `frontend/src/lib/stores/range.ts`, `frontend/src/lib/components/RangeSelector.svelte`, `frontend/src/lib/stores/auth.ts`, `Dashboard.svelte`, `TopPage.svelte`
- Test: `frontend/src/lib/stores/range.test.ts` (new), `frontend/src/lib/components/RangeSelector.test.ts` (new)

**Interfaces:**
- Produces: `type RangeSel = { kind: 'rolling'; key: '24h' | '7d' | '30d' | '365d' | 'all' } | { kind: 'calendar'; key: 'this_week' | 'this_month' | 'this_year' | 'last_week' | 'last_month' | 'last_year' } | { kind: 'custom'; from: string; to: string }`; `range: Writable<RangeSel>` persisted as JSON under `tw-range-v2`, falling back to the legacy `tw-range` mapping `day→24h, week→7d, month→30d, year→365d, all→all`, default `30d`.
- Produces: `function toParams(sel: RangeSel, tz: string, now: Date): StatsParams`: rolling → `since`; calendar `this_*` → `start` (local date in `tz` via `Intl.DateTimeFormat('en-CA', { timeZone: tz })`) + `calendar`; `last_*` → `start`, `end`, `calendar`; custom → `start: from`, `end: to + 1 day`. Weeks start Monday.
- Produces: `function bucketFor(sel: RangeSel, tz: string, now: Date): Bucket`: `day` up to 92 days, else `month`; `function rangeLabel(sel): string`.
- Produces: `rangeQuery: Readable<{ params: StatsParams; bucket: Bucket; compare: boolean }>` derived from `range` and `auth` (`compare` false for `all`).
- `auth.ts`: `loadMe` sends `api.updateMe({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })` once when `me.timezone` is null and stores the result.

- [ ] Write `range.test.ts`: `this_month` in `Europe/Berlin` at `2026-11-06T12:00Z` → `{ start: '2026-11-01', calendar: 'month' }`; `last_week` on Friday 2026-11-06 → `{ start: '2026-10-26', end: '2026-11-02', calendar: 'week' }`; `this_year` at `2026-12-31T23:30Z` in Berlin → `start: '2027-01-01'`; custom `2026-10-01..2026-10-31` → `end: '2026-11-01'`; legacy `month` maps to `30d`. `RangeSelector.test.ts`: choosing "Custom" shows two date inputs, and applying them updates the store.
- [ ] Run, expect FAIL. Implement the store, the selector (a `<select>` with optgroups Rolling / Calendar / Custom, plus two `type="date"` inputs and an Apply button for custom), and switch `Dashboard`/`TopPage` to `$rangeQuery`. Labels as in the spec ("Last 24 hours" … "Last year", "Custom…").
- [ ] `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): add calendar and custom ranges`.

### Task 14: Settings menu and reconnect banner

**Files:**
- Create: `frontend/src/lib/components/UserMenu.svelte`, `frontend/src/lib/components/ReconnectBanner.svelte`, tests next to them
- Modify: `frontend/src/routes/(app)/+layout.svelte`, `frontend/src/lib/format.ts`

**Interfaces:**
- Consumes: `api.me`, `api.updateMe`, `api.logout`, `auth` store.
- Produces: `formatRelative(iso: string, now: Date): string` ("just now", "3 min ago", "2 h ago", "4 days ago").
- `UserMenu`: button with the username; popover with "Synced 3 min ago" or "Importing your history…" (when `last_synced_at` is null), a timezone `<select>` over `Intl.supportedValuesOf('timeZone')`, "Log out". `ReconnectBanner`: shown when `$auth.user?.disconnected`; text "Last.fm access was revoked. Reconnect to keep tracking." and a link "Reconnect" to `/auth/login`.

- [ ] Write tests: `UserMenu` shows "Importing your history…" for null sync, "Synced 3 min ago" otherwise, changing the timezone calls `PATCH /auth/me`; `ReconnectBanner` renders only when disconnected; `formatRelative` cases.
- [ ] Run, expect FAIL. Implement; header order: range selector, share popover, user menu, theme toggle.
- [ ] `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): add a settings menu with sync status and a reconnect banner`.

### Task 15: Share popover

**Files:**
- Modify: `frontend/src/lib/components/ShareManager.svelte`, `ShareManager.test.ts`

**Interfaces:**
- Consumes: `api.listShares`, `api.createShare(body)`, `api.revokeShare`, `range`, `toParams`, `rangeLabel`.
- "Current range" maps the selection to the create body: rolling → `range_from = since`, `range_to = now`; calendar and custom → `start`/`end` from `toParams` (the backend resolves them and freezes an open end at now). "All time" sends no range.
- Popover: list rows (label or "Untitled", range text or "All time", Copy, Revoke), form with label input and a choice "All time" / "Current range (<rangeLabel>)", Create.

- [ ] Write tests: list loads on open, revoke removes the row, creating with "Current range" for `this_month` posts `start` and no `end`, for `30d` posts `range_from` and `range_to`, empty list shows "No active links".
- [ ] Run, expect FAIL. Implement. `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): manage share links in a popover`.

### Task 16: Comparison on stat cards

**Files:**
- Modify: `frontend/src/lib/components/StatCard.svelte`, `Dashboard.svelte`, tests

**Interfaces:**
- `StatCard` gets `delta?: number | null` (fraction, e.g. `0.12`); renders "+12 % vs. previous" / "−8 % vs. previous", up/down colour, nothing when null. `Dashboard` requests `summary(params, compare)` and computes `delta = previous ? (cur - prev) / prev : null`, null when `prev` is 0. No comparison with `token`.

- [ ] Tests: delta renders with sign, hidden for null and for share mode.
- [ ] Run, expect FAIL. Implement. `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): show change against the previous period`.

### Task 17: Covers and links to detail pages

**Files:**
- Create: `frontend/src/lib/components/Cover.svelte`, `frontend/src/lib/links.ts`, tests
- Modify: `TopList.svelte`, `RecentList.svelte`, `Dashboard.svelte`, `TopPage.svelte`

**Interfaces:**
- Produces in `links.ts`: `artistHref(base: string, artist: string)`, `albumHref(base, artist, album)`, `trackHref(base, artist, track)` → `${base}/artist?artist=…` etc., built with `URLSearchParams`.
- `Cover`: props `src: string | null | undefined`, `alt: string`, `size: number`; placeholder on null and on `error`.
- `TopList` items gain `href?: string` and `image?: string | null`; label becomes a link when `href` is set; cover shown when the list is created with `covers={true}`. Platform icons stay. Unknown-album rows get no `href`.
- `RecentList`: cover, track title links to the track page, artist to the artist page.

- [ ] Tests: `links.ts` round-trip for `AC/DC & "Friends" #1 ?+ Ünïcode` (parse the href with `URL` and read the params back), `Cover` swaps to the placeholder on `error`, `TopList` renders a link for items with `href`.
- [ ] Run, expect FAIL. Implement. `$W pnpm test && $W pnpm check`, expect green.
- [ ] Commit `feat(frontend): show covers and link rows to detail pages`.

### Task 18: Detail pages

**Files:**
- Create: `frontend/src/lib/components/ArtistPage.svelte`, `AlbumPage.svelte`, `TrackPage.svelte`, tests; routes `frontend/src/routes/(app)/{artist,album,track}/+page.svelte` and `frontend/src/routes/s/[token]/{artist,album,track}/+page.svelte`

**Interfaces:**
- Consumes: `statsApi(token).artist/album/track`, filtered `topTracks`, `topAlbums`, `metricsOverTime`, `recent`; `Cover`, `AreaTrend`, `TopList`, `RecentList`, `PlatformLinks`, `links.ts`, `rangeQuery`, `formatDuration`.
- Each page reads its identity from `$page.url.searchParams`; a 404 shows "Nothing found for <name>." Content per spec §6; first/last listen as local dates.

- [ ] Tests per page: renders header stats from a mocked detail response; shows the not-found text on 404; in share mode calls `/shared/<t>/…`.
- [ ] Run, expect FAIL. Implement. `$W pnpm test && $W pnpm check && $W pnpm build`, expect green.
- [ ] Commit `feat(frontend): add artist, album and track pages`.

### Task 19: Insights page

**Files:**
- Create: `frontend/src/lib/components/InsightsPage.svelte`, `OnThisDay.svelte`, `Records.svelte`, `Heatmap.svelte`, `Discoveries.svelte`, tests; routes `frontend/src/routes/(app)/insights/+page.svelte`, `frontend/src/routes/s/[token]/insights/+page.svelte`
- Modify: `frontend/src/lib/components/Nav.svelte` (and the share layout's link list)

**Interfaces:**
- Consumes: `statsApi(token).onThisDay/records/heatmap/discoveries`, `rangeQuery`, `Cover`, `links.ts`.
- Order on the page: on this day, streaks and records, heatmap, discoveries. Discoveries hidden for "All time". `Heatmap`: inline SVG, one column per week (Monday first), five shades from `--surface0` towards `--accent`, `<title>` per cell "2026-11-06: 14 listens".
- Nav: "Insights" after "Albums" in both modes.

- [ ] Tests: each section renders mocked data and its empty state; heatmap draws one cell per day in the window and shades the busiest cell darkest; nav shows "Insights".
- [ ] Run, expect FAIL. Implement. `$W pnpm test && $W pnpm check && $W pnpm build`, expect green.
- [ ] Commit `feat(frontend): add an insights page`.

### Task 20: End-to-end check

- [ ] Backend suite, ruff, mypy; frontend test, check, build: all green.
- [ ] Regenerate `openapi.json`/`schema.d.ts` once more; `git diff --exit-code frontend/src/lib/api/schema.d.ts` must be clean.
- [ ] Run the stack locally (backend on 8080 with `alembic upgrade head`, Vite dev on 5173 proxying to it), seed a user with listens across two years via `upsert_listens`, log in with a cookie from `SessionCodec`, and open overview, a detail page, insights and a share link with Playwright (screenshots at scale 1). Run `pnpm test:e2e -- --trace off`.
- [ ] Commit only if something had to change.
