from __future__ import annotations

from typing import Any, Callable, Awaitable, NoReturn
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette import status

from backend.src.services.slack.database import operations as ops
from backend.src.services.slack.database.schema import (
    User,
    Channel,
    ChannelMember,
    Message,
    UserTeam,
)


class SlackAPIError(Exception):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _session(request: Request):
    session = getattr(request.state, "db_session", None)
    if session is None:
        raise SlackAPIError(
            "missing database session", status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return session


def _principal(request: Request) -> dict[str, Any]:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise SlackAPIError("missing principal context", status.HTTP_401_UNAUTHORIZED)
    return principal


def _principal_user_id(request: Request) -> int:
    session = _session(request)
    impersonate_user_id = getattr(request.state, "impersonate_user_id", None)
    impersonate_email = getattr(request.state, "impersonate_email", None)
    if impersonate_user_id is not None and str(impersonate_user_id).strip() != "":
        try:
            return int(impersonate_user_id)
        except Exception:
            _slack_error("user_not_found")
    if impersonate_email:
        row = (
            session.execute(select(User).where(User.email == impersonate_email))
            .scalars()
            .first()
        )
        if row is not None:
            return int(row.user_id)
        _slack_error("user_not_found")
    _slack_error("user_not_found")


def _json_response(
    data: dict[str, Any], status_code: int = status.HTTP_200_OK
) -> JSONResponse:
    return JSONResponse(data, status_code=status_code)


def _slack_error(
    code: str, *, status_code: int = status.HTTP_400_BAD_REQUEST
) -> NoReturn:
    raise SlackAPIError(code, status_code)


def _parse_ts(ts: str) -> int:
    if ts is None:
        raise SlackAPIError("timestamp required")
    try:
        # Slack TS format: "12345.6789" -> store as integer microseconds
        if "." in ts:
            major, minor = ts.split(".", 1)
            return int(major) * 1_000_000 + int(minor)
        return int(ts)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise SlackAPIError("invalid timestamp format") from exc


def _format_ts(message_id: int | None) -> str | None:
    if message_id is None:
        return None
    # store as integer microseconds
    seconds, micros = divmod(int(message_id), 1_000_000)
    return f"{seconds}.{micros:06d}"


def _format_channel_id(channel_id: int) -> str:
    return f"C{channel_id:08d}"


def _format_user_id(user_id: int) -> str:
    return f"U{user_id:08d}"


def _resolve_channel_id(channel: str) -> int:
    if channel.startswith("C"):
        return int(channel[1:])
    return int(channel)


def _get_env_team_id(
    request: Request, *, channel_id: int | None, actor_user_id: int
) -> int:
    session = _session(request)
    if channel_id is not None:
        ch = session.get(Channel, channel_id)
        if ch is None:
            _slack_error("channel_not_found")
        return int(ch.team_id or 0)
    membership = (
        session.execute(select(UserTeam).where(UserTeam.user_id == actor_user_id))
        .scalars()
        .first()
    )
    if membership is None:
        _slack_error("user_not_found")
    return int(membership.team_id)


async def chat_post_message(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    text = payload.get("text")
    thread_ts = payload.get("thread_ts")
    session = _session(request)
    user_id = _principal_user_id(request)

    if not channel or not text:
        raise SlackAPIError("channel and text are required fields")

    channel_id = _resolve_channel_id(channel)
    # Validate channel and membership
    ch = session.get(Channel, channel_id)
    if ch is None:
        _slack_error("channel_not_found")
    if getattr(ch, "is_archived", False):
        _slack_error("is_archived")
    if session.get(ChannelMember, (channel_id, int(user_id))) is None:
        _slack_error("not_in_channel")

    message = ops.send_message(
        session=session,
        channel_id=channel_id,
        user_id=int(user_id),
        message_text=text,
        parent_id=_parse_ts(thread_ts) if thread_ts else None,
    )
    session.flush()

    return _json_response(
        {
            "ok": True,
            "channel": channel,
            "ts": _format_ts(message.message_id),
            "message": {
                "type": "message",
                "user": _format_user_id(message.user_id),
                "text": message.message_text,
                "ts": _format_ts(message.message_id),
            },
        }
    )


async def chat_update(request: Request) -> JSONResponse:
    payload = await request.json()
    ts = payload.get("ts")
    text = payload.get("text")
    channel = payload.get("channel")
    if not ts or not text or not channel:
        raise SlackAPIError("channel, ts, and text are required")

    session = _session(request)
    actor_id = _principal_user_id(request)
    channel_id = _resolve_channel_id(channel)
    msg = session.get(Message, _parse_ts(ts))
    if msg is None or msg.channel_id != channel_id:
        _slack_error("message_not_found", status_code=status.HTTP_404_NOT_FOUND)
    if msg.user_id != actor_id:
        _slack_error("cant_update_message")
    message = ops.update_message(session=session, message_id=_parse_ts(ts), text=text)
    session.flush()
    return _json_response(
        {
            "ok": True,
            "channel": channel,
            "ts": _format_ts(message.message_id),
            "message": {
                "type": "message",
                "user": _format_user_id(message.user_id),
                "text": message.message_text,
                "ts": _format_ts(message.message_id),
            },
        }
    )


async def chat_delete(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    ts = payload.get("ts")
    if not channel or not ts:
        raise SlackAPIError("channel and ts are required")

    session = _session(request)
    actor_id = _principal_user_id(request)
    channel_id = _resolve_channel_id(channel)
    msg = session.get(Message, _parse_ts(ts))
    if msg is None or msg.channel_id != channel_id:
        _slack_error("message_not_found", status_code=status.HTTP_404_NOT_FOUND)
    if msg.user_id != actor_id:
        _slack_error("cant_delete_message")
    ops.delete_message(session=session, message_id=_parse_ts(ts))
    session.flush()
    return _json_response({"ok": True, "channel": channel, "ts": ts})


async def conversations_create(request: Request) -> JSONResponse:
    payload = await request.json()
    name = payload.get("name")
    is_private = payload.get("is_private", False)
    if not name:
        _slack_error("invalid_name")
    session = _session(request)
    actor_id = _principal_user_id(request)
    team_id = _get_env_team_id(request, channel_id=None, actor_user_id=actor_id)
    try:
        channel_obj = ops.create_channel(
            session=session, channel_name=name, team_id=int(team_id)
        )
        if is_private:
            channel_obj.is_private = True
        session.flush()
        return _json_response(
            {
                "ok": True,
                "channel": {
                    "id": _format_channel_id(channel_obj.channel_id),
                    "name": channel_obj.channel_name,
                    "is_private": channel_obj.is_private,
                    "created": channel_obj.created_at.isoformat()
                    if channel_obj.created_at
                    else None,
                },
            }
        )
    except IntegrityError:
        _slack_error("name_taken")


async def conversations_list(request: Request) -> JSONResponse:
    params = request.query_params
    limit = int(params.get("limit", 100))
    cursor = int(params.get("cursor", 0) or 0)
    session = _session(request)
    user_id = _principal_user_id(request)
    team_id = _get_env_team_id(request, channel_id=None, actor_user_id=user_id)
    channels = ops.list_user_channels(
        session=session, user_id=int(user_id), team_id=int(team_id)
    )
    data = [
        {
            "id": _format_channel_id(ch.channel_id),
            "name": ch.channel_name,
            "is_private": ch.is_private,
            "is_archived": ch.is_archived,
        }
        for ch in channels[cursor : cursor + limit]
    ]
    next_cursor = str(cursor + limit) if cursor + limit < len(channels) else ""
    return _json_response(
        {
            "ok": True,
            "channels": data,
            "response_metadata": {"next_cursor": next_cursor},
        }
    )


async def conversations_history(request: Request) -> JSONResponse:
    params = request.query_params
    channel = params.get("channel")
    limit = int(params.get("limit", 100))
    cursor = int(params.get("cursor", 0) or 0)
    if not channel:
        _slack_error("channel_not_found")
    channel = str(channel)
    session = _session(request)
    channel_id = _resolve_channel_id(channel)
    # membership check
    actor_id = _principal_user_id(request)
    if session.get(ChannelMember, (channel_id, actor_id)) is None:
        _slack_error("not_in_channel")
    team_id = _get_env_team_id(request, channel_id=channel_id, actor_user_id=actor_id)
    messages = ops.list_channel_history(
        session=session,
        channel_id=channel_id,
        user_id=actor_id,
        team_id=int(team_id),
        limit=limit,
        offset=cursor,
    )
    response = {
        "ok": True,
        "messages": [
            {
                "type": "message",
                "user": _format_user_id(msg.user_id),
                "text": msg.message_text,
                "ts": _format_ts(msg.message_id),
                "thread_ts": _format_ts(msg.parent_id) if msg.parent_id else None,
            }
            for msg in messages
        ],
        "has_more": len(messages) == limit,
        "response_metadata": {
            "next_cursor": str(cursor + limit) if len(messages) == limit else ""
        },
    }
    return _json_response(response)


async def conversations_join(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    if channel is None:
        _slack_error("channel_not_found")
    session = _session(request)
    channel_id = _resolve_channel_id(channel)
    actor = _principal_user_id(request)
    existed = session.get(ChannelMember, (channel_id, actor)) is not None
    if not existed:
        ops.join_channel(session=session, channel_id=channel_id, user_id=actor)
        session.flush()
    return _json_response(
        {"ok": True, "channel": {"id": channel}, "already_in_channel": existed}
    )


async def conversations_invite(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    users = payload.get("users", [])
    if channel is None or not users:
        raise SlackAPIError("channel and users are required")
    session = _session(request)
    invited = []
    for user in users:
        member = ops.invite_user_to_channel(
            session=session, channel_id=_resolve_channel_id(channel), user_id=int(user)
        )
        invited.append({"id": _format_user_id(member.user_id)})
    session.flush()
    return _json_response(
        {"ok": True, "channel": {"id": str(channel)}, "invited": invited}
    )


async def conversations_kick(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    user = payload.get("user")
    if channel is None or user is None:
        raise SlackAPIError("channel and user are required")
    session = _session(request)
    ops.kick_user_from_channel(
        session=session, channel_id=_resolve_channel_id(channel), user_id=int(user)
    )
    session.flush()
    return _json_response({"ok": True})


async def conversations_leave(request: Request) -> JSONResponse:
    payload = await request.json()
    channel = payload.get("channel")
    if channel is None:
        raise SlackAPIError("channel is required")
    session = _session(request)
    ch_id = _resolve_channel_id(channel)
    actor = _principal_user_id(request)
    if session.get(ChannelMember, (ch_id, actor)) is None:
        _slack_error("not_in_channel")
    ops.leave_channel(session=session, channel_id=ch_id, user_id=actor)
    session.flush()
    return _json_response({"ok": True})


async def reactions_add(request: Request) -> JSONResponse:
    payload = await request.json()
    name = payload.get("name")
    channel = payload.get("channel") or payload.get("channel_id")
    ts = payload.get("timestamp") or payload.get("ts")
    if not name or not channel or not ts:
        _slack_error("invalid_arguments")
    session = _session(request)
    actor = _principal_user_id(request)
    msg = session.get(Message, _parse_ts(ts))
    if msg is None:
        _slack_error("no_item")
    ch_id = _resolve_channel_id(channel)
    if msg.channel_id != ch_id:
        _slack_error("no_item")
    if session.get(ChannelMember, (ch_id, actor)) is None:
        _slack_error("not_in_channel")
    existing = [
        r
        for r in ops.get_reactions(session=session, message_id=msg.message_id)
        if r.user_id == actor and r.reaction_type == name
    ]
    if existing:
        _slack_error("already_reacted")
    ops.add_emoji_reaction(
        session=session,
        message_id=msg.message_id,
        user_id=actor,
        reaction_type=name,
    )
    session.flush()
    return _json_response({"ok": True})


async def reactions_remove(request: Request) -> JSONResponse:
    payload = await request.json()
    name = payload.get("name")
    channel = payload.get("channel") or payload.get("channel_id")
    ts = payload.get("timestamp") or payload.get("ts")
    if not name or not ts or not channel:
        _slack_error("invalid_arguments")
    session = _session(request)
    reactions = ops.get_reactions(session=session, message_id=_parse_ts(ts))
    found = next(
        (
            r
            for r in reactions
            if r.user_id == _principal_user_id(request) and r.reaction_type == name
        ),
        None,
    )
    if not found:
        _slack_error("no_reaction", status_code=status.HTTP_404_NOT_FOUND)
    assert found is not None
    ops.remove_emoji_reaction(
        session=session,
        user_id=_principal_user_id(request),
        reaction_id=found.reaction_id,
    )
    session.flush()
    return _json_response({"ok": True})


async def reactions_get(request: Request) -> JSONResponse:
    params = request.query_params
    channel = params.get("channel")
    timestamp = params.get("timestamp")
    if not channel or not timestamp:
        raise SlackAPIError("channel and timestamp are required")
    session = _session(request)
    reactions = ops.get_reactions(session=session, message_id=_parse_ts(timestamp))
    return _json_response(
        {
            "ok": True,
            "type": "message",
            "channel": channel,
            "message": {
                "reactions": [
                    {
                        "name": reaction.reaction_type,
                        "count": 1,
                        "users": [_format_user_id(reaction.user_id)],
                    }
                    for reaction in reactions
                ]
            },
        }
    )


async def users_info(request: Request) -> JSONResponse:
    params = request.query_params
    user = params.get("user")
    if user is None:
        raise SlackAPIError("user is required")
    session = _session(request)
    user_row = ops.get_user(session=session, user_id=int(user))
    return _json_response({"ok": True, "user": _serialize_user(user_row)})


async def users_list(request: Request) -> JSONResponse:
    params = request.query_params
    limit = int(params.get("limit", 100))
    cursor = int(params.get("cursor", 0) or 0)
    session = _session(request)
    actor = _principal_user_id(request)
    team_id = _get_env_team_id(request, channel_id=None, actor_user_id=actor)
    users = ops.list_users(session=session, team_id=int(team_id))
    page = users[cursor : cursor + limit]
    next_cursor = str(cursor + limit) if cursor + limit < len(users) else ""
    return _json_response(
        {
            "ok": True,
            "members": [_serialize_user(u) for u in page],
            "response_metadata": {"next_cursor": next_cursor},
        }
    )


async def users_set_presence(request: Request) -> JSONResponse:
    payload = await request.json()
    presence = payload.get("presence")
    if presence not in {"active", "away"}:
        raise SlackAPIError("presence must be 'active' or 'away'")
    # Presence is accepted and echoed; not persisted in DB for MVP
    return _json_response({"ok": True, "presence": presence})


def _serialize_user(user) -> dict[str, Any]:
    return {
        "id": _format_user_id(user.user_id),
        "name": user.username,
        "real_name": user.real_name,
        "profile": {
            "display_name": user.display_name,
            "real_name": user.real_name,
            "email": user.email,
            "title": user.title,
            "image_72": user.avatar_url,
        },
        "tz": user.timezone,
        "is_bot": False,
        "deleted": not user.is_active,
        "presence": "active",
    }


async def users_conversations(request: Request) -> JSONResponse:
    params = request.query_params
    limit = int(params.get("limit", 100))
    cursor = int(params.get("cursor", 0) or 0)
    session = _session(request)
    actor = _principal_user_id(request)
    user_param = params.get("user")
    target_user = int(user_param) if user_param is not None else actor
    team_id = _get_env_team_id(request, channel_id=None, actor_user_id=target_user)
    channels = ops.list_user_channels(
        session=session, user_id=target_user, team_id=team_id
    )
    page = channels[cursor : cursor + limit]
    next_cursor = str(cursor + limit) if cursor + limit < len(channels) else ""
    data = [
        {
            "id": _format_channel_id(ch.channel_id),
            "name": ch.channel_name,
            "is_private": ch.is_private,
            "is_archived": ch.is_archived,
        }
        for ch in page
    ]
    return _json_response(
        {
            "ok": True,
            "channels": data,
            "response_metadata": {"next_cursor": next_cursor},
        }
    )


async def slack_endpoint(request: Request) -> JSONResponse:
    endpoint = request.path_params["endpoint"]
    handler = SLACK_HANDLERS.get(endpoint)
    if handler is None:
        return JSONResponse(
            {"ok": False, "error": "unsupported_endpoint"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    try:
        response = await handler(request)
        return response
    except SlackAPIError as exc:
        return JSONResponse(
            {"ok": False, "error": exc.detail}, status_code=exc.status_code
        )
    except Exception:  # pragma: no cover - defensive
        return JSONResponse(
            {"ok": False, "error": "internal_error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


SLACK_HANDLERS: dict[str, Callable[[Request], Awaitable[JSONResponse]]] = {
    "chat.postMessage": chat_post_message,
    "chat.update": chat_update,
    "chat.delete": chat_delete,
    "conversations.create": conversations_create,
    "conversations.list": conversations_list,
    "conversations.history": conversations_history,
    "conversations.join": conversations_join,
    "conversations.invite": conversations_invite,
    "conversations.kick": conversations_kick,
    "conversations.leave": conversations_leave,
    "reactions.add": reactions_add,
    "reactions.remove": reactions_remove,
    "reactions.get": reactions_get,
    "users.info": users_info,
    "users.list": users_list,
    "users.conversations": users_conversations,
    "users.setPresence": users_set_presence,
}


routes = [Route("/{endpoint}", slack_endpoint, methods=["GET", "POST"])]
