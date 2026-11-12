"""weekly report week

Adds users.weekly_report_week, the Monday of the last week a report
went out for, so an hourly job sends each week's report once.

Users with a webhook start with the week the previous chart default
(Mondays at 08:00 Europe/Berlin) last sent them, so an upgrade on a
Monday does not send that week a second time.

Revision ID: c8cc26e5b57f
Revises: e1f7b3a95c20
Create Date: 2026-11-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8cc26e5b57f'
down_revision: Union[str, Sequence[str], None] = 'e1f7b3a95c20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LAST_SENT_BY_THE_WEEKLY_JOB = """
UPDATE users SET weekly_report_week = (
    date_trunc('week', last_run.at AT TIME ZONE
        CASE WHEN users.timezone IN (SELECT name FROM pg_timezone_names)
        THEN users.timezone ELSE 'UTC' END) - interval '7 days'
)::date
FROM (
    SELECT (CASE WHEN berlin >= date_trunc('week', berlin) + interval '8 hours'
        THEN date_trunc('week', berlin) + interval '8 hours'
        ELSE date_trunc('week', berlin) - interval '7 days' + interval '8 hours' END)
        AT TIME ZONE 'Europe/Berlin' AS at
    FROM (SELECT now() AT TIME ZONE 'Europe/Berlin' AS berlin) AS clock
) AS last_run
WHERE users.discord_webhook_url IS NOT NULL
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('weekly_report_week', sa.Date(), nullable=True))
    op.execute(_LAST_SENT_BY_THE_WEEKLY_JOB)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'weekly_report_week')
