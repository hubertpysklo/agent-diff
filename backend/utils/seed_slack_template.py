#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.services.slack.database.base import Base


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

    temp_engine = create_engine(
        db_url.replace(
            "/diff_the_universe",
            f"/diff_the_universe?options=-csearch_path%3D{template_schema}",
        )
    )

    Base.metadata.create_all(temp_engine, checkfirst=True)
    print(f"Created tables in {template_schema}")


if __name__ == "__main__":
    main()
