import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import Listen
from tidalwave.models.domain import Scrobble
from tidalwave.reports.weekly import last_full_week, send_weekly_reports, weekly_embed

MONDAY_8_BERLIN = datetime(2026, 11, 9, 7, 0, tzinfo=UTC)
WEEK_START = datetime(2026, 11, 1, 23, 0, tzinfo=UTC)
BASE = "https://tidalwave.example"


def test_last_full_week_is_monday_to_monday_in_the_users_timezone():
    assert last_full_week("Europe/Berlin", MONDAY_8_BERLIN) == (
        WEEK_START, datetime(2026, 11, 8, 23, 0, tzinfo=UTC),
    )


def test_last_full_week_follows_daylight_saving_changes():
    # 07:00Z on Monday is still Sunday evening in Los Angeles, whose clocks
    # went back on 1 November.
    assert last_full_week("America/Los_Angeles", MONDAY_8_BERLIN) == (
        datetime(2026, 10, 26, 7, 0, tzinfo=UTC), datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
    )


def test_last_full_week_in_utc_mid_week():
    assert last_full_week("UTC", datetime(2026, 11, 12, 15, tzinfo=UTC)) == (
        datetime(2026, 11, 2, tzinfo=UTC), datetime(2026, 11, 9, tzinfo=UTC),
    )


def _at(hours_after_week_start: float, artist: str, track: str) -> Scrobble:
    return Scrobble(artist=artist, track_title=track, album=None,
                    played_at=WEEK_START + timedelta(hours=hours_after_week_start))


async def _with_durations(db_session, user_id: int, scrobbles: list[Scrobble], seconds: int):
    await upsert_listens(db_session, user_id, scrobbles)
    for s in scrobbles:
        listen = (await db_session.execute(
            Listen.__table__.select().where(
                Listen.user_id == user_id, Listen.played_at == s.played_at
            )
        )).one()
        await db_session.execute(
            Listen.__table__.update().where(Listen.id == listen.id).values(duration_sec=seconds)
        )


async def _seed_week(db_session, user):
    previous = [_at(-1 - i, "Kavinsky", "Nightcall") for i in range(5)]
    await _with_durations(db_session, user.id, previous, 240)
    this_week = [
        _at(10, "Kavinsky", "Nightcall"), _at(11, "Kavinsky", "Nightcall"),
        _at(12, "Kavinsky", "Nightcall"), _at(13, "Kavinsky", "Roadgame"),
    ]
    await _with_durations(db_session, user.id, this_week, 240)
    new = [_at(20, "Timecop1983", "On the Run"), _at(21, "Timecop1983", "On the Run")]
    await _with_durations(db_session, user.id, new, 300)
    await upsert_listens(db_session, user.id, [_at(7 * 24 + 0.5, "Daft Punk", "Aerodynamic")])
    await db_session.flush()


async def test_the_embed_sums_up_the_week_against_the_one_before(db_session):
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    alice.timezone = "Europe/Berlin"
    await _seed_week(db_session, alice)

    embed = await weekly_embed(db_session, alice, now=MONDAY_8_BERLIN, base_url=BASE)

    assert embed is not None
    assert embed["title"] == "Your week in music"
    assert embed["description"] == "Nov 2 – 8, 2026"
    assert embed["url"] == BASE
    assert embed["timestamp"] == "2026-11-08T23:00:00+00:00"
    assert embed["footer"] == {"text": "tidalwave · week 45"}
    assert {f["name"]: f["value"] for f in embed["fields"]} == {
        "Listening time": "26m (+30% on the week before)",
        "Listens": "6 (+20% on the week before)",
        "Top artist": "Kavinsky, 4 listens",
        "Top track": "Nightcall by Kavinsky, 3 listens",
        "New discoveries": "Timecop1983",
    }


async def test_a_week_without_listens_gets_no_embed(db_session):
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, alice.id, [_at(-3, "Kavinsky", "Nightcall")])
    await db_session.flush()

    assert await weekly_embed(db_session, alice, now=MONDAY_8_BERLIN, base_url=BASE) is None


async def test_first_week_and_unknown_durations_read_plainly(db_session):
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    alice.timezone = "Europe/Berlin"
    await upsert_listens(db_session, alice.id, [
        _at(1, "*NSYNC", "Bye Bye Bye"), _at(1.5, "*NSYNC", "Bye Bye Bye"),
        *[_at(2 + i, f"Artist {i}", "Song") for i in range(7)],
    ])
    await db_session.flush()

    embed = await weekly_embed(db_session, alice, now=MONDAY_8_BERLIN, base_url=BASE)

    assert embed is not None
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Listening time"] == "Not known yet"
    assert fields["Listens"] == "9 (none the week before)"
    assert fields["Top artist"] == "\\*NSYNC, 2 listens"
    assert fields["Top track"] == "Bye Bye Bye by \\*NSYNC, 2 listens"
    assert fields["New discoveries"] == (
        "\\*NSYNC, Artist 0, Artist 1, Artist 2, Artist 3 and 3 more"
    )


@respx.mock
async def test_reports_go_to_every_webhook_and_one_failure_stops_nobody(db_session):
    hooks = {
        name: f"https://discord.com/api/webhooks/{i}/token{i}"
        for i, name in enumerate(["bob", "alice", "carol"], start=1)
    }
    users = {}
    for name in ["bob", "alice", "carol", "dave"]:
        user = await upsert_user_from_session(db_session, name, "sk", mode="open", allowlist=[])
        user.discord_webhook_url = hooks.get(name)
        users[name] = user
    for name in ["bob", "alice", "dave"]:
        await upsert_listens(db_session, users[name].id, [_at(5, "Kavinsky", "Nightcall")])
    await db_session.flush()
    failing = respx.post(hooks["bob"]).respond(500)
    sent = respx.post(hooks["alice"]).respond(204)
    empty = respx.post(hooks["carol"]).respond(204)

    async with httpx.AsyncClient() as http:
        report = await send_weekly_reports(
            db_session, http, now=MONDAY_8_BERLIN + timedelta(hours=2), base_url=BASE
        )

    assert report == {"bob": "failed", "alice": "sent", "carol": "empty"}
    assert failing.called and sent.called and not empty.called
    assert users["alice"].weekly_report_week == date(2026, 11, 2)
    assert users["bob"].weekly_report_week is None
    assert users["carol"].weekly_report_week is None
    body = json.loads(sent.calls.last.request.content)
    assert body["embeds"][0]["fields"][1] == {
        "name": "Listens", "value": "1 (none the week before)", "inline": True,
    }
    assert body["embeds"][0]["fields"][3]["value"] == "Nightcall by Kavinsky, 1 listen"


HOOK = "https://discord.com/api/webhooks/1/token1"


async def _subscriber(db_session, tz: str, *listens: datetime):
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    alice.timezone = tz
    alice.discord_webhook_url = HOOK
    await upsert_listens(db_session, alice.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None, played_at=at)
        for at in listens
    ])
    await db_session.flush()
    return alice


async def _run(db_session, now: datetime) -> dict[str, str]:
    async with httpx.AsyncClient() as http:
        return await send_weekly_reports(db_session, http, now=now, base_url=BASE)


@respx.mock
@pytest.mark.parametrize(("tz", "seven_on_monday", "sunday_evening", "monday", "label"), [
    ("Pacific/Honolulu", datetime(2026, 11, 9, 17, tzinfo=UTC),
     datetime(2026, 11, 9, 6, tzinfo=UTC), date(2026, 11, 2), "Nov 2 – 8, 2026"),
    ("UTC", datetime(2026, 11, 9, 7, tzinfo=UTC),
     datetime(2026, 11, 8, 20, tzinfo=UTC), date(2026, 11, 2), "Nov 2 – 8, 2026"),
    ("Pacific/Kiritimati", datetime(2026, 11, 8, 17, tzinfo=UTC),
     datetime(2026, 11, 8, 6, tzinfo=UTC), date(2026, 11, 2), "Nov 2 – 8, 2026"),
    # Berlin's clocks went back on Sunday, 25 October.
    ("Europe/Berlin", datetime(2026, 10, 26, 6, tzinfo=UTC),
     datetime(2026, 10, 25, 22, 30, tzinfo=UTC), date(2026, 10, 19), "Oct 19 – 25, 2026"),
], ids=["utc-10", "utc+0", "utc+14", "dst-change"])
async def test_the_report_goes_out_from_eight_on_the_users_monday_for_the_week_just_ended(
    db_session, tz, seven_on_monday, sunday_evening, monday, label
):
    alice = await _subscriber(db_session, tz, sunday_evening)
    hook = respx.post(HOOK).respond(204)

    assert await _run(db_session, seven_on_monday + timedelta(minutes=59)) == {}
    assert not hook.called
    assert alice.weekly_report_week is None

    assert await _run(db_session, seven_on_monday + timedelta(hours=1)) == {"alice": "sent"}
    embed = json.loads(hook.calls.last.request.content)["embeds"][0]
    assert embed["description"] == label
    assert {f["name"]: f["value"] for f in embed["fields"]}["Listens"] == (
        "1 (none the week before)"
    )
    assert alice.weekly_report_week == monday


@respx.mock
async def test_a_run_hours_late_still_sends_once_that_monday(db_session):
    alice = await _subscriber(db_session, "Europe/Berlin", datetime(2026, 11, 8, 12, tzinfo=UTC))
    hook = respx.post(HOOK).respond(204)

    assert await _run(db_session, datetime(2026, 11, 9, 12, 5, tzinfo=UTC)) == {"alice": "sent"}
    for hour in (13, 14, 22):
        assert await _run(db_session, datetime(2026, 11, 9, hour, 5, tzinfo=UTC)) == {}
    assert hook.call_count == 1
    assert alice.weekly_report_week == date(2026, 11, 2)


@respx.mock
async def test_two_runs_in_the_same_hour_send_once(db_session):
    await _subscriber(db_session, "Europe/Berlin", datetime(2026, 11, 8, 12, tzinfo=UTC))
    hook = respx.post(HOOK).respond(204)

    assert await _run(db_session, datetime(2026, 11, 9, 7, 5, tzinfo=UTC)) == {"alice": "sent"}
    assert await _run(db_session, datetime(2026, 11, 9, 7, 40, tzinfo=UTC)) == {}
    assert hook.call_count == 1


@respx.mock
async def test_a_post_discord_refused_is_tried_again_the_next_hour(db_session):
    alice = await _subscriber(db_session, "UTC", datetime(2026, 11, 8, 12, tzinfo=UTC))
    hook = respx.post(HOOK).mock(side_effect=[httpx.Response(500), httpx.Response(204)])

    assert await _run(db_session, datetime(2026, 11, 9, 8, 5, tzinfo=UTC)) == {"alice": "failed"}
    assert alice.weekly_report_week is None
    assert await _run(db_session, datetime(2026, 11, 9, 9, 5, tzinfo=UTC)) == {"alice": "sent"}
    assert hook.call_count == 2
    assert alice.weekly_report_week == date(2026, 11, 2)


@respx.mock
async def test_only_mondays_send_and_the_next_monday_sends_the_next_week(db_session):
    alice = await _subscriber(
        db_session, "UTC",
        datetime(2026, 11, 8, 12, tzinfo=UTC), datetime(2026, 11, 15, 12, tzinfo=UTC),
    )
    hook = respx.post(HOOK).respond(204)

    assert await _run(db_session, datetime(2026, 11, 10, 9, 5, tzinfo=UTC)) == {}
    assert await _run(db_session, datetime(2026, 11, 15, 9, 5, tzinfo=UTC)) == {}
    assert not hook.called

    assert await _run(db_session, datetime(2026, 11, 16, 8, 5, tzinfo=UTC)) == {"alice": "sent"}
    assert alice.weekly_report_week == date(2026, 11, 9)
