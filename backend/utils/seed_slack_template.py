#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.services.slack.database.base import Base
from src.services.slack.database import schema as slack_schema


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(db_url)

    template_schema = "slack_template"

    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {template_schema}"))
        print(f"Created schema: {template_schema}")

    with engine.connect() as conn:
        conn = conn.execution_options(schema_translate_map={None: template_schema})

        _ = slack_schema

        # print(f"Creating {len(Base.metadata.tables)} tables...")
        # for table_name in Base.metadata.tables.keys():
        #    print(f"  - {table_name}")

        Base.metadata.create_all(conn, checkfirst=True)
        conn.commit()

    print(f"Created tables in {template_schema}")


if __name__ == "__main__":
    main()
