"""add created_by fields

Revision ID: c8d4f92a1b3e
Revises: b43581216cd9
Create Date: 2025-01-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d4f92a1b3e'
down_revision: Union[str, None] = 'b43581216cd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('run_time_environments', sa.Column('created_by', sa.String(length=255), nullable=False), schema='public')
    op.create_foreign_key(None, 'run_time_environments', 'users', ['created_by'], ['id'], source_schema='public', referent_schema='public')

    op.add_column('test_runs', sa.Column('created_by', sa.String(length=255), nullable=False), schema='public')
    op.create_foreign_key(None, 'test_runs', 'users', ['created_by'], ['id'], source_schema='public', referent_schema='public')


def downgrade() -> None:
    op.drop_constraint(None, 'test_runs', schema='public', type_='foreignkey')
    op.drop_column('test_runs', 'created_by', schema='public')

    op.drop_constraint(None, 'run_time_environments', schema='public', type_='foreignkey')
    op.drop_column('run_time_environments', 'created_by', schema='public')
