from ariadne.asgi import GraphQL
from backend.src.platform.isolationEngine.core import CoreIsolationEngine
from backend.src.platform.evaluationEngine.core import CoreEvaluationEngine


class GraphQLWithSession(GraphQL):
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
        path_parts = request.scope.get("path", "").split("/")
        # expected: /api/env/{env_id}/services/linear/graphql
        env_id = path_parts[3] if len(path_parts) > 3 else None
        if not env_id:
            raise PermissionError("missing environment identifier in path")
        session = self.coreIsolationEngine.sessions.get_session_for_environment(env_id)
        request.state.db_session = session
        request.state.environment_id = env_id
        return {"request": request, "session": session, "environment_id": env_id}

    async def handle_request(self, request):
        try:
            resp = await super().handle_request(request)
            if request.state.db_session:
                request.state.db_session.commit()
            return resp
        except Exception:
            if request.state.db_session:
                request.state.db_session.rollback()
            raise
        finally:
            if request.state.db_session:
                request.state.db_session.close()
                request.state.db_session = None
