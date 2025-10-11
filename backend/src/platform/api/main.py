from sqlalchemy import create_engine
from backend.src.platform.isolationEngine.session import SessionManager
from starlette.applications import Starlette
from os import environ
from backend.src.platform.isolationEngine.core import CoreIsolationEngine
from backend.src.platform.evaluationEngine.core import CoreEvaluationEngine
from backend.src.platform.isolationEngine.environment import EnvironmentHandler
from backend.src.platform.api.routes import routes as platform_routes
from starlette.routing import Router


def create_app():
    app = Starlette()
    db_url = environ["DATABASE_URL"]

    platform_engine = create_engine(db_url, pool_pre_ping=True)
    sessions = SessionManager(platform_engine)
    environment_handler = EnvironmentHandler(session_manager=sessions)

    coreIsolationEngine = CoreIsolationEngine(
        sessions=sessions, environment_handler=environment_handler
    )
    coreEvaluationEngine = CoreEvaluationEngine(sessions=sessions)

    app.state.coreIsolationEngine = coreIsolationEngine
    app.state.coreEvaluationEngine = coreEvaluationEngine
    app.state.sessions = sessions

    platform_router = Router(platform_routes)
    app.mount("/api/platform", platform_router)

    return app
