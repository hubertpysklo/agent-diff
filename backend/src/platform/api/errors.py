import json
from typing import TypeVar, Type

from pydantic import BaseModel, ValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.platform.api.models import APIError

T = TypeVar("T", bound=BaseModel)


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


async def parse_request_body(request: Request, model: Type[T]) -> T:
    try:
        data = await request.json()
    except json.JSONDecodeError as e:
        raise ValueError("invalid json") from e

    try:
        return model(**data)
    except ValidationError as e:
        raise ValueError(f"validation error: {str(e)}") from e
