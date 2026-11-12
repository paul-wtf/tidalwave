"""comparisons

Adds compare_invites, single-use tokens a user hands to someone else, and
compare_pairs, the two users who accepted to compare their listening.

Revision ID: b3e9f2c71d04
Revises: a7c41e9d2b58
Create Date: 2026-11-12 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e9f2c71d04'
down_revision: Union[str, Sequence[str], None] = 'a7c41e9d2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'compare_invites',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=43), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_compare_invites_user_id'), 'compare_invites', ['user_id'], unique=False)
    op.create_table(
        'compare_pairs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('low_user_id', sa.Integer(), nullable=False),
        sa.Column('high_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('low_user_id < high_user_id', name='ck_compare_pair_order'),
        sa.ForeignKeyConstraint(['low_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['high_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('low_user_id', 'high_user_id', name='uq_compare_pair'),
    )
    op.create_index(op.f('ix_compare_pairs_high_user_id'), 'compare_pairs', ['high_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_compare_pairs_high_user_id'), table_name='compare_pairs')
    op.drop_table('compare_pairs')
    op.drop_index(op.f('ix_compare_invites_user_id'), table_name='compare_invites')
    op.drop_table('compare_invites')
