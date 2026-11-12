"""share range key

Adds shares.range_key: the symbolic range of a share that moves with time.

Revision ID: d4e8f1a29b73
Revises: b7c3d9e41a62
Create Date: 2026-11-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8f1a29b73'
down_revision: Union[str, Sequence[str], None] = 'b7c3d9e41a62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('shares', sa.Column('range_key', sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('shares', 'range_key')
