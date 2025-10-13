#!/usr/bin/env python3
"""
Seed script for creating Slack template schemas.

Creates two templates:
- slack_base: Empty schema with tables only
- slack_default: Pre-populated with default test data

Usage:
    python backend/utils/seed_slack_template.py
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.services.slack.database.base import Base
from src.services.slack.database import schema as slack_schema

# Tables in foreign key dependency order
TABLE_ORDER = [
    "teams",
    "users",
    "channels",
    "user_teams",
    "channel_members",
    "messages",
    "message_reactions",
]


def create_schema(conn, schema_name: str):
    """Create a PostgreSQL schema."""
    conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
    conn.execute(text(f"CREATE SCHEMA {schema_name}"))


def create_tables(conn, schema_name: str):
    """Create all tables in the schema using SQLAlchemy metadata."""
    conn_with_schema = conn.execution_options(schema_translate_map={None: schema_name})
    _ = slack_schema  # Ensure all models are loaded
    Base.metadata.create_all(conn_with_schema, checkfirst=True)


def insert_seed_data(conn, schema_name: str, seed_data: dict):
    """Insert seed data into tables using dynamic SQL.

    Args:
        conn: Database connection
        schema_name: Target schema name
        seed_data: Dict mapping table names to lists of records
    """
    for table_name in TABLE_ORDER:
        if table_name not in seed_data:
            continue

        records = seed_data[table_name]
        if not records:
            continue

        print(f"  Inserting {len(records)} {table_name}...")

        for record in records:
            columns = ", ".join(record.keys())
            placeholders = ", ".join([f":{k}" for k in record.keys()])
            sql = f"INSERT INTO {schema_name}.{table_name} ({columns}) VALUES ({placeholders})"
            conn.execute(text(sql), record)


def create_template(engine, template_name: str, seed_file: Path | None = None):
    """Create a template schema with optional seed data.

    Args:
        engine: SQLAlchemy engine
        template_name: Name of the schema to create
        seed_file: Optional path to JSON seed file
    """
    print(f"\n=== Creating {template_name} ===")

    with engine.begin() as conn:
        create_schema(conn, template_name)
        print(f"Created schema: {template_name}")

        create_tables(conn, template_name)
        print(f"Created {len(Base.metadata.tables)} tables")

        if seed_file:
            if not seed_file.exists():
                print(f"Seed file not found: {seed_file}")
                return

            with open(seed_file) as f:
                seed_data = json.load(f)

            insert_seed_data(conn, template_name, seed_data)
            print(f"Loaded seed data from {seed_file.name}")
        else:
            print(f"Empty template ready")


def main():
    """Create both slack_base and slack_default templates."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    engine = create_engine(db_url)
    seeds_dir = Path(__file__).parent.parent.parent / "examples" / "slack" / "seeds"

    # Create empty base template
    create_template(engine, "slack_base")

    # Create default template with seed data
    create_template(engine, "slack_default", seeds_dir / "slack_default.json")

    print("\n All templates created successfully\n")


if __name__ == "__main__":
    main()
