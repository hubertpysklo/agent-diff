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

    examples_root = Path(__file__).resolve().parent.parent.parent / "examples"

    # Discover all test suite JSON files
    test_suite_files = list(examples_root.glob("*/testsuites/*.json"))

    if not test_suite_files:
        print("No test suite files found in examples/*/testsuites/")
        return

    engine = create_engine(db_url)

    with Session(engine) as session:
        if session.query(Test).count() > 0:
            print("Tests already exist, skipping")
            return

        for test_file in test_suite_files:
            print(
                f"Loading test suite from {test_file.relative_to(examples_root.parent)}"
            )

            with open(test_file) as f:
                data = json.load(f)

            # Create test suite for dev user
            test_suite = TestSuite(
                name=data.get("name", test_file.stem),
                description=data.get(
                    "description", f"Test suite from {test_file.name}"
                ),
                owner="dev-user",
                visibility="public",
            )
            session.add(test_suite)
            session.flush()

            # Create tests and link to suite
            test_count = 0
            for test_data in data.get("tests", []):
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
                test_count += 1

            print(f"  → Loaded {test_count} tests in suite '{test_suite.name}'")

        session.commit()
        print(f"\nSuccessfully seeded {len(test_suite_files)} test suite(s)")


if __name__ == "__main__":
    main()
