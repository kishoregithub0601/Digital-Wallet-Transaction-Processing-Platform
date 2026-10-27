"""add refresh tokens

Revision ID: 994cfa347edc
Revises: 5f993fcce38b
Create Date: 2026-10-26 15:18:46.322870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '994cfa347edc'
down_revision: Union[str, Sequence[str], None] = '5f993fcce38b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
