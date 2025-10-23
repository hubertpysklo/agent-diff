"""

Add 'public' to owner_scope enum (map existing 'global' -> 'public').

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7d9e2f1aabc"
down_revision: Union[str, None] = "b8115b19688d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enum type with desired values
    op.execute("CREATE TYPE owner_scope_new AS ENUM ('public','org','user')")

    # Convert column to new type, mapping legacy 'global' -> 'public'
    op.execute(
        """
        ALTER TABLE public.environments
        ALTER COLUMN owner_scope
        TYPE owner_scope_new
        USING (
            CASE
                WHEN owner_scope::text = 'global' THEN 'public'::owner_scope_new
                ELSE owner_scope::text::owner_scope_new
            END
        )
        """
    )

    # Swap types: rename old to _old, new to canonical, drop old
    op.execute("ALTER TYPE owner_scope RENAME TO owner_scope_old")
    op.execute("ALTER TYPE owner_scope_new RENAME TO owner_scope")
    op.execute("DROP TYPE owner_scope_old")

    # Align default with model
    op.execute(
        "ALTER TABLE public.environments ALTER COLUMN owner_scope SET DEFAULT 'public'"
    )


def downgrade() -> None:
    # Recreate old type
    op.execute("CREATE TYPE owner_scope_old AS ENUM ('global','org','user')")

    # Convert back, mapping 'public' -> 'global'
    op.execute(
        """
        ALTER TABLE public.environments
        ALTER COLUMN owner_scope
        TYPE owner_scope_old
        USING (
            CASE
                WHEN owner_scope::text = 'public' THEN 'global'::owner_scope_old
                ELSE owner_scope::text::owner_scope_old
            END
        )
        """
    )

    # Swap back
    op.execute("ALTER TYPE owner_scope RENAME TO owner_scope_new")
    op.execute("ALTER TYPE owner_scope_old RENAME TO owner_scope")
    op.execute("DROP TYPE owner_scope_new")

    # Restore default
    op.execute(
        "ALTER TABLE public.environments ALTER COLUMN owner_scope SET DEFAULT 'global'"
    )
