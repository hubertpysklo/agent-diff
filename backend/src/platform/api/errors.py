from starlette import status
from starlette.responses import JSONResponse

from src.platform.api.models import APIError


def bad_request(detail: str) -> JSONResponse:
    return JSONResponse(
        APIError(detail=detail).model_dump(mode="json"),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def not_found(detail: str) -> JSONResponse:
    return JSONResponse(
        APIError(detail=detail).model_dump(mode="json"),
        status_code=status.HTTP_404_NOT_FOUND,
    )


def conflict(detail: str) -> JSONResponse:
    return JSONResponse(
        APIError(detail=detail).model_dump(mode="json"),
        status_code=status.HTTP_409_CONFLICT,
    )


def unauthorized(detail: str = "unauthorized") -> JSONResponse:
    return JSONResponse(
        APIError(detail=detail).model_dump(mode="json"),
        status_code=status.HTTP_403_FORBIDDEN,
    )
