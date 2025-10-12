from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette import status

from backend.src.platform.isolationEngine.session import SessionManager
from backend.src.platform.isolationEngine.core import CoreIsolationEngine
from backend.src.platform.api.auth import validate_api_key
from backend.src.platform.db.schema import RunTimeEnvironment


class IsolationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        session_manager: SessionManager,
        core_isolation_engine: CoreIsolationEngine,
    ):
        super().__init__(app)
        self.session_manager = session_manager
        self.core_isolation_engine = core_isolation_engine

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path", "")
        # Expected: /api/env/{env_id}/services/{service}/...
        if not path.startswith("/api/env/"):
            return await call_next(request)

        try:
            path_after_prefix = path[len("/api/env/") :]
            env_id = path_after_prefix.split("/")[0] if path_after_prefix else ""

            if not env_id:
                return JSONResponse(
                    {"ok": False, "error": "invalid_environment_path"},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            api_key_hdr = request.headers.get("X-API-Key") or request.headers.get(
                "Authorization"
            )
            if not api_key_hdr:
                return JSONResponse(
                    {"ok": False, "error": "not_authed"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            with self.session_manager.with_meta_session() as meta_session:
                principal: dict[str, Any] = validate_api_key(api_key_hdr, meta_session)
                request.state.principal = principal

                try:
                    env_uuid = self.session_manager._to_uuid(env_id)
                    env = (
                        meta_session.query(RunTimeEnvironment)
                        .filter(RunTimeEnvironment.id == env_uuid)
                        .one_or_none()
                    )
                    if env is not None:
                        request.state.impersonate_user_id = env.impersonate_user_id
                        request.state.impersonate_email = env.impersonate_email
                except (ValueError, TypeError):
                    pass

            with self.session_manager.with_session_for_environment(env_id) as session:
                request.state.db_session = session
                request.state.environment_id = env_id

                try:
                    response = await call_next(request)

                    if not (200 <= response.status_code < 400):
                        session.rollback()

                    return response
                finally:
                    request.state.db_session = None
                    request.state.environment_id = None
                    request.state.impersonate_user_id = None
                    request.state.impersonate_email = None

        except PermissionError as exc:
            return JSONResponse(
                {"ok": False, "error": str(exc)},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return JSONResponse(
                {"ok": False, "error": "internal_error"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
