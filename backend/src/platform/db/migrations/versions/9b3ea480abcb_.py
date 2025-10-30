"""

Revision ID: 9b3ea480abcb
Revises: 24fedf2ade30
Create Date: 2025-10-29 04:53:42.669493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9b3ea480abcb'
down_revision: Union[str, None] = '24fedf2ade30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('run_time_environments_created_by_fkey'), 'run_time_environments', type_='foreignkey')
    op.drop_constraint(op.f('test_runs_created_by_fkey'), 'test_runs', type_='foreignkey')
    op.drop_constraint(op.f('test_suites_owner_fkey'), 'test_suites', type_='foreignkey')

    op.drop_table('api_keys')
    op.drop_table('organization_memberships')
    op.drop_table('organizations')
    op.drop_table('users')

    op.drop_constraint(op.f('diffs_environment_id_fkey'), 'diffs', type_='foreignkey')
    op.create_foreign_key(None, 'diffs', 'run_time_environments', ['environment_id'], ['id'], source_schema='public', referent_schema='public')

    template_visibility = postgresql.ENUM('public', 'private', name='template_visibility', create_type=True)
    template_visibility.create(op.get_bind(), checkfirst=True)

    op.add_column('environments', sa.Column('visibility', sa.Enum('public', 'private', name='template_visibility'), nullable=False, server_default='public'))
    op.add_column('environments', sa.Column('owner_id', sa.String(length=255), nullable=True))
    op.drop_constraint(op.f('uq_environments_identity'), 'environments', type_='unique')
    op.create_unique_constraint('uq_environments_identity', 'environments', ['service', 'name', 'version', 'owner_id'], schema='public')
    op.drop_column('environments', 'owner_user_id')
    op.drop_column('environments', 'owner_org_id')
    op.drop_column('environments', 'owner_scope')

    op.drop_constraint(op.f('test_memberships_test_id_fkey'), 'test_memberships', type_='foreignkey')
    op.drop_constraint(op.f('test_memberships_test_suite_id_fkey'), 'test_memberships', type_='foreignkey')
    op.create_foreign_key(None, 'test_memberships', 'test_suites', ['test_suite_id'], ['id'], source_schema='public', referent_schema='public')
    op.create_foreign_key(None, 'test_memberships', 'tests', ['test_id'], ['id'], source_schema='public', referent_schema='public')

    op.drop_constraint(op.f('test_runs_test_suite_id_fkey'), 'test_runs', type_='foreignkey')
    op.drop_constraint(op.f('test_runs_test_id_fkey'), 'test_runs', type_='foreignkey')
    op.drop_constraint(op.f('test_runs_environment_id_fkey'), 'test_runs', type_='foreignkey')
    op.create_foreign_key(None, 'test_runs', 'run_time_environments', ['environment_id'], ['id'], source_schema='public', referent_schema='public')
    op.create_foreign_key(None, 'test_runs', 'test_suites', ['test_suite_id'], ['id'], source_schema='public', referent_schema='public')
    op.create_foreign_key(None, 'test_runs', 'tests', ['test_id'], ['id'], source_schema='public', referent_schema='public')


def downgrade() -> None:
    op.create_foreign_key(op.f('test_suites_owner_fkey'), 'test_suites', 'users', ['owner'], ['id'])
    op.drop_constraint(None, 'test_runs', schema='public', type_='foreignkey')
    op.drop_constraint(None, 'test_runs', schema='public', type_='foreignkey')
    op.drop_constraint(None, 'test_runs', schema='public', type_='foreignkey')
    op.create_foreign_key(op.f('test_runs_environment_id_fkey'), 'test_runs', 'run_time_environments', ['environment_id'], ['id'])
    op.create_foreign_key(op.f('test_runs_created_by_fkey'), 'test_runs', 'users', ['created_by'], ['id'])
    op.create_foreign_key(op.f('test_runs_test_id_fkey'), 'test_runs', 'tests', ['test_id'], ['id'])
    op.create_foreign_key(op.f('test_runs_test_suite_id_fkey'), 'test_runs', 'test_suites', ['test_suite_id'], ['id'])
    op.drop_constraint(None, 'test_memberships', schema='public', type_='foreignkey')
    op.drop_constraint(None, 'test_memberships', schema='public', type_='foreignkey')
    op.create_foreign_key(op.f('test_memberships_test_suite_id_fkey'), 'test_memberships', 'test_suites', ['test_suite_id'], ['id'])
    op.create_foreign_key(op.f('test_memberships_test_id_fkey'), 'test_memberships', 'tests', ['test_id'], ['id'])
    op.create_foreign_key(op.f('run_time_environments_created_by_fkey'), 'run_time_environments', 'users', ['created_by'], ['id'])
    op.add_column('environments', sa.Column('owner_scope', postgresql.ENUM('public', 'org', 'user', name='owner_scope'), server_default=sa.text("'public'::owner_scope"), autoincrement=False, nullable=False))
    op.add_column('environments', sa.Column('owner_org_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('environments', sa.Column('owner_user_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_constraint('uq_environments_identity', 'environments', schema='public', type_='unique')
    op.create_unique_constraint(op.f('uq_environments_identity'), 'environments', ['service', 'owner_scope', 'owner_org_id', 'owner_user_id', 'name', 'version'], postgresql_nulls_not_distinct=False)
    op.drop_column('environments', 'owner_id')
    op.drop_column('environments', 'visibility')
    op.drop_constraint(None, 'diffs', schema='public', type_='foreignkey')
    op.create_foreign_key(op.f('diffs_environment_id_fkey'), 'diffs', 'run_time_environments', ['environment_id'], ['id'])
    op.create_table('api_keys',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('key_hash', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('key_salt', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('expires_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('revoked_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('user_id', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('last_used_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('api_keys_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('api_keys_pkey'))
    )
    op.create_table('organizations',
    sa.Column('id', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='organizations_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_table('users',
    sa.Column('id', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('email', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('username', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('password', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('is_platform_admin', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('is_organization_admin', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='users_pkey'),
    sa.UniqueConstraint('email', name='users_email_key', postgresql_include=[], postgresql_nulls_not_distinct=False),
    sa.UniqueConstraint('username', name='users_username_key', postgresql_include=[], postgresql_nulls_not_distinct=False),
    postgresql_ignore_search_path=False
    )
    op.create_table('organization_memberships',
    sa.Column('user_id', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('organization_id', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('organization_memberships_organization_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('organization_memberships_user_id_fkey')),
    sa.PrimaryKeyConstraint('user_id', 'organization_id', name=op.f('organization_memberships_pkey'))
    )
