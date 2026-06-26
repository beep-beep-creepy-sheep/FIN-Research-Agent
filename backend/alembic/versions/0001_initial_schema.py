"""initial complete schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op

from finresearch.database.models import Base


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
