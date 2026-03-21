"""empty message

Revision ID: e41153af4216
Revises: 31f5a9837529
Create Date: 2026-03-21 17:52:26.087997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e41153af4216'
down_revision: Union[str, Sequence[str], None] = '31f5a9837529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add API_PUSH value to source_type_enum."""
    op.execute("ALTER TYPE source_type_enum ADD VALUE IF NOT EXISTS 'API_PUSH'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values. No-op."""
    pass
