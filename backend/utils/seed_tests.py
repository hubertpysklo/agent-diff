#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.platform.db.schema import Test


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    test_file = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "slack"
        / "testsuites"
        / "slack_bench.json"
    )

    with open(test_file) as f:
        data = json.load(f)

    engine = create_engine(db_url)

    with Session(engine) as session:
        if not session.query(Test).exists():
            for test_data in data["tests"]:
                test = Test(
                    name=test_data["name"],
                    prompt=test_data["prompt"],
                    type=test_data["type"],
                    expected_output=test_data.get("assertions", []),
                    template_schema=test_data.get("seed_template"),
                    impersonate_user_id=test_data.get("impersonate_user_id"),
                )
                session.add(test)
            print(f"Loaded {len(data['tests'])} tests")
        else:
            print("Tests already exist, skipping")
            return

        session.commit()


if __name__ == "__main__":
    main()
