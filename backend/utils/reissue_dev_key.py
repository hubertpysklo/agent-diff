"""Reissue dev API key."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select
from src.platform.db.schema import User, ApiKey
from src.platform.api.auth import KeyHandler
from src.platform.isolationEngine.session import SessionManager


def reissue_dev_key():
    """Delete old dev API keys and generate a new one."""
    engine = create_engine(os.environ["DATABASE_URL"])
    session_manager = SessionManager(engine)
    key_handler = KeyHandler(session_manager)

    try:
        with session_manager.with_meta_session() as session:
            user = session.execute(
                select(User).where(User.email == "dev@localhost")
            ).scalar_one()

            old_keys = (
                session.execute(select(ApiKey).where(ApiKey.user_id == user.id))
                .scalars()
                .all()
            )

            for key in old_keys:
                session.delete(key)

            session.commit()

        key_data = key_handler.create_api_key(user_id=user.id)

        print(f"\nNew Dev API Key: {key_data.token}\n")

    except Exception as e:
        print(f"\nError reissuing key: {e}\n")
        raise


if __name__ == "__main__":
    reissue_dev_key()
