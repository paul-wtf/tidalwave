"""album years

Adds album_years: the release year of an album from MusicBrainz, cached
globally.

Revision ID: f6b28d4c0e35
Revises: e5a17c3b9d24
Create Date: 2026-11-12 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b28d4c0e35'
down_revision: Union[str, Sequence[str], None] = 'e5a17c3b9d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'album_years',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('artist', sa.Text(), nullable=False),
        sa.Column('album', sa.Text(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artist', 'album', name='uq_album_year'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('album_years')
