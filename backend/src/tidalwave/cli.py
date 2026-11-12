from __future__ import annotations

import argparse
import asyncio
import logging

import httpx
from sqlalchemy import select

from tidalwave.config import Settings
from tidalwave.db import make_engine, make_session_factory, session_scope
from tidalwave.ingest.covers import fill_missing_covers
from tidalwave.ingest.durations import fill_missing_durations
from tidalwave.ingest.poller import poll_all_users
from tidalwave.ingest.service import backfill_user
from tidalwave.ingest.tags import fill_missing_artist_tags
from tidalwave.ingest.years import fill_missing_album_years
from tidalwave.lastfm.client import LastfmClient
from tidalwave.models.db import User
from tidalwave.musicbrainz.client import MusicBrainzClient

# Per poll run, resolve at most this many new track durations so the 5-minute
# job stays bounded. Historical gaps are filled by `tidalwave-backfill-durations`.
_POLL_DURATION_BUDGET = 50
_POLL_COVER_BUDGET = 50
_POLL_TAG_BUDGET = 50


def _client(http: httpx.AsyncClient, settings: Settings) -> LastfmClient:
    return LastfmClient(http, api_key=settings.lastfm_api_key, api_secret=settings.lastfm_api_secret)


async def _poll() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        client = _client(http, settings)
        report = await poll_all_users(session, client)
        filled = await fill_missing_durations(session, client, max_tracks=_POLL_DURATION_BUDGET)
        covers = await fill_missing_covers(session, client, max_albums=_POLL_COVER_BUDGET)
        tagged = await fill_missing_artist_tags(session, client, max_artists=_POLL_TAG_BUDGET)
        # MusicBrainz takes a second per request. What Last.fm delivered is
        # saved first, so that a run cut short there loses no listens.
        await session.commit()
        years = await fill_missing_album_years(
            session,
            MusicBrainzClient(http, base_url=settings.musicbrainz_url),
            max_albums=settings.musicbrainz_budget,
        )
        await session.commit()
        log = logging.getLogger("tidalwave")
        log.info("poll report: %s", report)
        if filled:
            log.info("resolved durations for %s listens", filled)
        if covers:
            log.info("looked up covers for %s albums", covers)
        if tagged:
            log.info("looked up tags for %s artists", tagged)
        if years:
            log.info("looked up release years for %s albums", years)


async def _backfill(username: str) -> None:
    settings = Settings()
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        user = (
            await session.execute(select(User).where(User.lastfm_username == username))
        ).scalar_one()
        inserted = await backfill_user(session, _client(http, settings), user)
        await session.commit()
        logging.getLogger("tidalwave").info("backfilled %s listens for %s", inserted, username)


async def _backfill_durations(username: str | None) -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        user_id: int | None = None
        if username is not None:
            user = (
                await session.execute(select(User).where(User.lastfm_username == username))
            ).scalar_one()
            user_id = user.id
        filled = await fill_missing_durations(session, _client(http, settings), user_id=user_id)
        await session.commit()
        logging.getLogger("tidalwave").info("resolved durations for %s listens", filled)


async def _backfill_covers() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        written = await fill_missing_covers(session, _client(http, settings))
        await session.commit()
        logging.getLogger("tidalwave").info("looked up covers for %s albums", written)


async def _backfill_tags() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        written = await fill_missing_artist_tags(session, _client(http, settings))
        await session.commit()
        logging.getLogger("tidalwave").info("looked up tags for %s artists", written)


async def _backfill_years() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    factory = make_session_factory(make_engine(settings))
    async with httpx.AsyncClient(timeout=15.0) as http, session_scope(factory) as session:
        client = MusicBrainzClient(http, base_url=settings.musicbrainz_url)
        written = await fill_missing_album_years(session, client)
        await session.commit()
        logging.getLogger("tidalwave").info("looked up release years for %s albums", written)


def poll() -> None:
    asyncio.run(_poll())


def backfill() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    asyncio.run(_backfill(args.username))


def backfill_durations() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve missing track durations from Last.fm (all users, or one)."
    )
    parser.add_argument("username", nargs="?", default=None)
    args = parser.parse_args()
    asyncio.run(_backfill_durations(args.username))


def backfill_covers() -> None:
    argparse.ArgumentParser(
        description="Look up missing album covers on Last.fm."
    ).parse_args()
    asyncio.run(_backfill_covers())


def backfill_tags() -> None:
    argparse.ArgumentParser(
        description="Look up missing artist genre tags on Last.fm."
    ).parse_args()
    asyncio.run(_backfill_tags())


def backfill_years() -> None:
    argparse.ArgumentParser(
        description="Look up missing album release years on MusicBrainz, one per second."
    ).parse_args()
    asyncio.run(_backfill_years())
