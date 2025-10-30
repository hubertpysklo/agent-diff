#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.platform.db.schema import Test, TestSuite, TestMembership


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    test_file = (
        Path(__file__).resolve().parent.parent.parent
        / "examples"
        / "slack"
        / "testsuites"
        / "slack_bench.json"
    )

    with open(test_file) as f:
        data = json.load(f)

    engine = create_engine(db_url)

    with Session(engine) as session:
        if session.query(Test).count() > 0:
            print("Tests already exist, skipping")
            return

        # Create test suite for dev user
        test_suite = TestSuite(
            name=data.get("name", "Slack Benchmark Suite"),
            description=data.get("description", "Default Slack test suite"),
            owner="dev-user",
            visibility="public",
        )
        session.add(test_suite)
        session.flush()

        # Create tests and link to suite
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
            session.flush()

            membership = TestMembership(
                test_id=test.id,
                test_suite_id=test_suite.id,
            )
            session.add(membership)

        print(f"Loaded {len(data['tests'])} tests in suite '{test_suite.name}'")
        session.commit()


if __name__ == "__main__":
    main()
