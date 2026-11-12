from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from test_migrations import _sql, scratch  # noqa: F401

from tidalwave.stats.scope import last_full_week

BERLIN = ZoneInfo("Europe/Berlin")


def _last_monday_run(now: datetime) -> datetime:
    local = now.astimezone(BERLIN)
    run = (local - timedelta(days=local.weekday())).replace(hour=8, minute=0, second=0,
                                                             microsecond=0)
    if run > local:
        run -= timedelta(days=7)
    return run.astimezone(UTC)


async def test_users_with_a_webhook_start_with_the_week_the_monday_job_last_sent(scratch):  # noqa: F811
    conn, _ = scratch
    await conn.execute(_sql("upgrade", "e1f7b3a95c20"))
    await conn.execute(
        "INSERT INTO users (lastfm_username, lastfm_session_key, timezone, discord_webhook_url) "
        "VALUES ('berlin', 'sk', 'Europe/Berlin', 'https://discord.com/api/webhooks/1/a'), "
        "('honolulu', 'sk', 'Pacific/Honolulu', 'https://discord.com/api/webhooks/2/b'), "
        "('nozone', 'sk', NULL, 'https://discord.com/api/webhooks/3/c'), "
        "('nohook', 'sk', 'Europe/Berlin', NULL)"
    )
    now = datetime.now(UTC)

    await conn.execute(_sql("upgrade", "e1f7b3a95c20:c8cc26e5b57f"))

    rows = await conn.fetch("SELECT lastfm_username, weekly_report_week FROM users")
    marked = {r["lastfm_username"]: r["weekly_report_week"] for r in rows}
    run = _last_monday_run(now)

    def sent(tz: str):
        return last_full_week(tz, run)[0].astimezone(ZoneInfo(tz)).date()

    assert marked == {
        "berlin": sent("Europe/Berlin"),
        "honolulu": sent("Pacific/Honolulu"),
        "nozone": sent("UTC"),
        "nohook": None,
    }
