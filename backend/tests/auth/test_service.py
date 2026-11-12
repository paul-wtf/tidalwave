import pytest
from sqlalchemy import func, select

from tidalwave.auth.registration import RegistrationDenied
from tidalwave.auth.service import upsert_user_from_session
from tidalwave.models.db import User


async def test_first_user_becomes_admin(db_session):
    user = await upsert_user_from_session(
        db_session, "alice", "sk1", mode="open", allowlist=[]
    )
    assert user.is_admin is True
    assert user.lastfm_session_key == "sk1"


async def test_existing_user_is_logged_in_and_key_refreshed(db_session):
    first = await upsert_user_from_session(db_session, "alice", "sk1", mode="open", allowlist=[])
    again = await upsert_user_from_session(db_session, "alice", "sk2", mode="open", allowlist=[])
    assert again.id == first.id
    assert again.lastfm_session_key == "sk2"
    assert again.disconnected is False
    count = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == 1


async def test_second_user_not_admin(db_session):
    await upsert_user_from_session(db_session, "alice", "sk1", mode="open", allowlist=[])
    bob = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    assert bob.is_admin is False


async def test_new_user_denied_when_not_on_allowlist(db_session):
    with pytest.raises(RegistrationDenied):
        await upsert_user_from_session(
            db_session, "mallory", "sk", mode="allowlist", allowlist=["alice"]
        )


async def test_new_user_on_the_runtime_allowlist_may_register_in_any_case(db_session):
    from tidalwave.models.db import AllowlistEntry

    db_session.add(AllowlistEntry(lastfm_username="Carol"))
    await db_session.flush()

    carol = await upsert_user_from_session(
        db_session, "cAROL", "sk", mode="allowlist", allowlist=["alice"]
    )

    assert carol.lastfm_username == "cAROL"


async def test_delete_account_removes_the_user(db_session):
    from tidalwave.auth.service import delete_account

    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    alice_id = alice.id

    await delete_account(db_session, alice)

    db_session.expire_all()
    assert await db_session.get(User, alice_id) is None
