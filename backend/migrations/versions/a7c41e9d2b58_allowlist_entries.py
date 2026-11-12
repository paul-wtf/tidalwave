"""allowlist entries

Adds allowlist_entries: Last.fm usernames an admin allowed to register at
runtime, unique regardless of case.

Revision ID: a7c41e9d2b58
Revises: f6b28d4c0e35
Create Date: 2026-11-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c41e9d2b58'
down_revision: Union[str, Sequence[str], None] = 'f6b28d4c0e35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'allowlist_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('lastfm_username', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_allowlist_entry_username',
        'allowlist_entries',
        [sa.literal_column('lower(lastfm_username)')],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_allowlist_entry_username', table_name='allowlist_entries')
    op.drop_table('allowlist_entries')
