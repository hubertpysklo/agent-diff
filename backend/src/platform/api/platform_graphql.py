import ariadne.asgi
from backend.src.platform.isolationEngine.session import SessionManager
from backend.src.platform.api.auth import validate_api_key


class PlatformGraphQL(ariadne.asgi.GraphQL):
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def context_value(self, request):
        session = self.session_manager.get_meta_session()
        try:
            api_key_hdr = request.headers.get("X-API-Key") or request.headers.get(
                "Authorization"
            )
            principal = validate_api_key(api_key_hdr, session)
            request.state.db_session = session
            request.state.principal = principal
            return {"request": request, "session": session, "principal": principal}
        except Exception:
            session.rollback()
            session.close()
            raise

    async def handle_request(self, request):
        try:
            response = await super().handle_request(request)
            if getattr(request.state, "db_session", None):
                request.state.db_session.commit()
            return response
        except Exception:
            if getattr(request.state, "db_session", None):
                request.state.db_session.rollback()
            raise
        finally:
            if getattr(request.state, "db_session", None):
                request.state.db_session.close()
                request.state.db_session = None
