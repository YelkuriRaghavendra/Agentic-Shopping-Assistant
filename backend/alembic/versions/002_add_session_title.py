"""add session title

Revision ID: 002
Revises: 001
Create Date: 2024-04-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add title column to sessions table
    op.add_column('sessions', sa.Column('title', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Remove title column from sessions table
    op.drop_column('sessions', 'title')
