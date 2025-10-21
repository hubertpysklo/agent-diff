from ariadne.asgi import GraphQL
from src.platform.isolationEngine.core import CoreIsolationEngine
from src.platform.evaluationEngine.core import CoreEvaluationEngine


class LinearGraphQL(GraphQL):
    """
    GraphQL handler for Linear service that uses isolated database sessions.

    This class integrates with the platform's IsolationMiddleware which:
    - Authenticates requests via API key
    - Extracts environment_id from URL path
    - Provides scoped database session for the environment
    """

    def __init__(
        self,
        schema,
        coreIsolationEngine: CoreIsolationEngine,
        coreEvaluationEngine: CoreEvaluationEngine,
    ):
        super().__init__(schema)
        self.coreIsolationEngine = coreIsolationEngine
        self.coreEvaluationEngine = coreEvaluationEngine

    async def context_value(self, request):
        """
        Extract context from request for GraphQL resolvers.

        IsolationMiddleware has already set:
        - request.state.db_session: Scoped to environment schema
        - request.state.environment_id: UUID of the environment
        - request.state.impersonate_user_id: User ID to impersonate (optional)
        - request.state.impersonate_email: User email to impersonate (optional)
        """
        session = getattr(request.state, "db_session", None)
        env_id = getattr(request.state, "environment_id", None)

        if not session:
            raise PermissionError(
                "missing database session - ensure IsolationMiddleware is active"
            )

        if not env_id:
            raise PermissionError("missing environment identifier")

        return {
            "request": request,
            "session": session,
            "environment_id": env_id,
            "user_id": getattr(request.state, "impersonate_user_id", None),
            "impersonate_email": getattr(request.state, "impersonate_email", None),
        }

    async def handle_request(self, request):
        return await super().handle_request(request)
