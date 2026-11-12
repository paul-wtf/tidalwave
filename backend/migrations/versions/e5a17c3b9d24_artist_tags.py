"""artist tags

Adds artist_tags: the genre tags of an artist from Last.fm, cached globally.

Revision ID: e5a17c3b9d24
Revises: d4e8f1a29b73
Create Date: 2026-11-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5a17c3b9d24'
down_revision: Union[str, Sequence[str], None] = 'd4e8f1a29b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'artist_tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('artist', sa.Text(), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artist', name='uq_artist_tags'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('artist_tags')
