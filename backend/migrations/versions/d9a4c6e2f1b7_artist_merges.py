"""artist merges

Adds listens.artist_raw, the spelling a listen arrived with, and the
artist_merges table. The dedup key moves to artist_raw, so rewriting
listens.artist to a merged name can never collide.

Revision ID: d9a4c6e2f1b7
Revises: c8d2a5f16e47
Create Date: 2026-11-12 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a4c6e2f1b7'
down_revision: Union[str, Sequence[str], None] = 'c8d2a5f16e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('listens', sa.Column('artist_raw', sa.Text(), nullable=True))
    op.execute('UPDATE listens SET artist_raw = artist')
    op.alter_column('listens', 'artist_raw', nullable=False)
    op.drop_constraint('uq_listen_dedup', 'listens', type_='unique')
    op.create_unique_constraint(
        'uq_listen_dedup', 'listens', ['user_id', 'artist_raw', 'track_title', 'played_at']
    )
    op.create_table(
        'artist_merges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('variant', sa.Text(), nullable=False),
        sa.Column('canonical', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'variant', name='uq_artist_merge_variant'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('artist_merges')
    op.drop_constraint('uq_listen_dedup', 'listens', type_='unique')
    op.execute('UPDATE listens SET artist = artist_raw')
    op.create_unique_constraint(
        'uq_listen_dedup', 'listens', ['user_id', 'artist', 'track_title', 'played_at']
    )
    op.drop_column('listens', 'artist_raw')
