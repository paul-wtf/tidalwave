"""imports

Adds the imports table and listens.source and listens.import_id, so a
listening history uploaded from Spotify or ListenBrainz can be told apart
and undone as a whole.

Revision ID: e1f7b3a95c20
Revises: d9a4c6e2f1b7
Create Date: 2026-11-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f7b3a95c20'
down_revision: Union[str, Sequence[str], None] = 'd9a4c6e2f1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'imports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('read', sa.Integer(), nullable=False),
        sa.Column('skipped', sa.Integer(), nullable=False),
        sa.Column('too_short', sa.Integer(), nullable=False),
        sa.Column('duplicates', sa.Integer(), nullable=False),
        sa.Column('added', sa.Integer(), nullable=False),
        sa.Column('first_played_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_played_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_imports_user_id', 'imports', ['user_id'])
    op.create_index(
        'uq_imports_one_active', 'imports', ['user_id'], unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.add_column(
        'listens',
        sa.Column(
            'source', sa.String(length=16), server_default=sa.text("'lastfm'"), nullable=False
        ),
    )
    op.add_column('listens', sa.Column('import_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'listens_import_id_fkey', 'listens', 'imports', ['import_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_listens_import_id', 'listens', ['import_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DELETE FROM listens WHERE import_id IS NOT NULL')
    op.drop_index('ix_listens_import_id', table_name='listens')
    op.drop_constraint('listens_import_id_fkey', 'listens', type_='foreignkey')
    op.drop_column('listens', 'import_id')
    op.drop_column('listens', 'source')
    op.drop_index('uq_imports_one_active', table_name='imports')
    op.drop_index('ix_imports_user_id', table_name='imports')
    op.drop_table('imports')
