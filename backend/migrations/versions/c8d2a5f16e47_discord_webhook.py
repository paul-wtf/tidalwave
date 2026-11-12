"""discord webhook

Adds users.discord_webhook_url, where the weekly report is posted.

Revision ID: c8d2a5f16e47
Revises: b3e9f2c71d04
Create Date: 2026-11-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d2a5f16e47'
down_revision: Union[str, Sequence[str], None] = 'b3e9f2c71d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('discord_webhook_url', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'discord_webhook_url')
