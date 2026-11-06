"""stats extensions

Adds users.timezone, shares.label, the album_art cache table and an
index on listens (user_id, artist, played_at).

Revision ID: b7c3d9e41a62
Revises: a1d2e3f40510
Create Date: 2026-11-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c3d9e41a62'
down_revision: Union[str, Sequence[str], None] = 'a1d2e3f40510'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('timezone', sa.String(length=64), nullable=True))
    op.add_column('shares', sa.Column('label', sa.Text(), nullable=True))
    op.create_table(
        'album_art',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('artist', sa.Text(), nullable=False),
        sa.Column('album', sa.Text(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artist', 'album', name='uq_album_art'),
    )
    op.create_index('ix_listens_user_artist_played', 'listens', ['user_id', 'artist', 'played_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_listens_user_artist_played', table_name='listens')
    op.drop_table('album_art')
    op.drop_column('shares', 'label')
    op.drop_column('users', 'timezone')
