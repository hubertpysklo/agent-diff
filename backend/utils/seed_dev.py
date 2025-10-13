#!/usr/bin/env python3
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.platform.db.schema import User, ApiKey
from src.platform.api.auth import KeyHandler
from src.platform.isolationEngine.session import SessionManager
from uuid import uuid4
from datetime import datetime


def main():
    if os.environ.get("ENV") != "development":
        sys.exit(0)

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url)
    session_manager = SessionManager(engine)

    with session_manager.with_meta_session() as session:
        existing_user = session.query(User).filter(User.email == "dev@localhost").first()

        if existing_user:
            user_id = existing_user.id
        else:
            user_id = str(uuid4())
            dev_user = User(
                id=user_id,
                email="dev@localhost",
                username="dev",
                password="dev",
                name="Dev User",
                is_platform_admin=True,
                is_organization_admin=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(dev_user)
            session.flush()

        existing_key = session.query(ApiKey).filter(ApiKey.user_id == user_id).first()

        if not existing_key or existing_key.revoked_at:
            key_handler = KeyHandler(session_manager)
            result = key_handler.create_api_key(
                user_id=int(user_id) if user_id.isdigit() else 1,
                days_valid=365,
                is_platform_admin=True,
                is_organization_admin=True,
            )
            print(f"\nDev API Key: {result['token']}\n")


if __name__ == "__main__":
    main()
