"""init schema

Revision ID: b43581216cd9
Revises:
Create Date: 2025-09-14 15:43:32.183049

"""

from typing import Sequence, Union


revision: str = "b43581216cd9"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This project seeds database schemas from template dumps rather than
    # Alembic migrations at the moment.  Placeholder kept for future diffs.


def downgrade() -> None:
    """Downgrade schema."""
    # Service schemas are managed via template refresh; no downgrade steps yet.
