from ariadne.asgi import GraphQL
from backend.src.platform.isolationEngine.core import CoreIsolationEngine
from backend.src.platform.evalutionEngine.core import CoreEvaluationEngine


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
        token = request.headers.get("Authorization")
        session = (
            self.coreIsolationEngine.get_session_for_token(token) if token else None
        )
        request.state.db_session = session
        return {"request": request, "session": session}

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
