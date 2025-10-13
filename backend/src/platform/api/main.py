from sqlalchemy import create_engine
from src.platform.isolationEngine.session import SessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from os import environ
from src.platform.isolationEngine.core import CoreIsolationEngine
from src.platform.evaluationEngine.core import CoreEvaluationEngine
from src.platform.isolationEngine.environment import EnvironmentHandler
from starlette.routing import Router
from src.platform.api.routes import routes as platform_routes
from src.platform.api.middleware import IsolationMiddleware, PlatformMiddleware
from src.services.slack.api.methods import routes as slack_routes


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

    platform_router = Router(
        routes=platform_routes,
        middleware=[Middleware(PlatformMiddleware, session_manager=sessions)],
    )
    app.mount("/api/platform", platform_router)

    app.add_middleware(
        IsolationMiddleware,
        session_manager=sessions,
        core_isolation_engine=coreIsolationEngine,
    )

    slack_router = Router(slack_routes)
    app.mount("/api/env/{env_id}/services/slack", slack_router)

    return app


app = create_app()
