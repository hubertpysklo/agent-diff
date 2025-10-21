from src.services.slack.database.schema import (
    User,
    Team,
    Channel,
    Message,
    ChannelMember,
    MessageReaction,
    UserTeam,
)

import secrets
import string
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, exists, and_
# Create Team


def create_team(
    session: Session,
    team_name: str,
    team_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    default_channel_name: str | None = None,
):
    # Generate team_id if not provided
    if team_id is None:
        # Generate Slack-style team ID: T + 10 alphanumeric chars
        chars = string.ascii_uppercase + string.digits
        team_id = "T" + "".join(secrets.choice(chars) for _ in range(10))

    team = Team(team_id=team_id, team_name=team_name)
    if created_at is not None:
        team.created_at = created_at
    session.add(team)
    if default_channel_name:
        # Generate channel_id for default channel
        channel_id = "C" + "".join(secrets.choice(chars) for _ in range(10))
        channel = Channel(
            channel_id=channel_id,
            channel_name=default_channel_name,
            team_id=team.team_id,
            is_private=False,
            is_dm=False,
            is_gc=False,
        )
        session.add(channel)
    return team


# Create User


def create_user(
    session: Session,
    username: str,
    email: str,
    user_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    real_name: str | None = None,
    display_name: str | None = None,
    timezone: str | None = None,
    title: str | None = None,
):
    # Generate user_id if not provided
    if user_id is None:
        # Generate Slack-style user ID: U + 10 alphanumeric chars
        chars = string.ascii_uppercase + string.digits
        user_id = "U" + "".join(secrets.choice(chars) for _ in range(10))

    user = User(
        user_id=user_id,
        username=username,
        email=email,
        real_name=real_name,
        display_name=display_name,
        timezone=timezone,
        title=title,
    )
    if created_at is not None:
        user.created_at = created_at
    session.add(user)
    return user


# create-channel


def create_channel(
    session: Session,
    channel_name: str,
    team_id: str,
    channel_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> Channel:
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")

    # Generate channel_id if not provided
    if channel_id is None:
        # Generate Slack-style channel ID: C + 10 alphanumeric chars
        chars = string.ascii_uppercase + string.digits
        channel_id = "C" + "".join(secrets.choice(chars) for _ in range(10))

    channel = Channel(
        channel_id=channel_id,
        channel_name=channel_name,
        team_id=team_id,
        is_private=False,
        is_dm=False,
        is_gc=False,
    )
    if created_at is not None:
        channel.created_at = created_at
    session.add(channel)
    return channel


# archive-channel


def archive_channel(session: Session, channel_id: str):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.is_archived = True
    return channel


# unarchive-channel


def unarchive_channel(session: Session, channel_id: str):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.is_archived = False
    return channel


# rename-channel


def rename_channel(session: Session, channel_id: str, new_name: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.channel_name = new_name
    return channel


# set-channel-topic


def set_channel_topic(session: Session, channel_id: str, topic: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.topic_text = topic
    return channel


# invite-user-to-channel


def invite_user_to_channel(
    session: Session,
    channel_id: str,
    user_id: str,
    joined_at: Optional[datetime] = None,
) -> ChannelMember:
    channel = session.get(Channel, channel_id)
    user = session.get(User, user_id)
    if channel is None:
        raise ValueError("Channel not found")
    if user is None:
        raise ValueError("User not found")
    existing = session.get(ChannelMember, (channel_id, user_id))
    if existing:
        return existing
    member = ChannelMember(channel_id=channel_id, user_id=user_id)
    if joined_at is not None:
        member.joined_at = joined_at
    session.add(member)
    return member


# kick-user-from-channel


def kick_user_from_channel(session: Session, channel_id: str, user_id: str):
    channel = session.get(Channel, channel_id)
    user = session.get(User, user_id)
    if channel is None or user is None:
        raise ValueError("Channel or user not found")
    channel_member = session.get(ChannelMember, (channel_id, user_id))
    if channel_member is None:
        raise ValueError("Channel member not found")
    session.delete(channel_member)
    return channel_member


# send-message


def send_message(
    session: Session,
    channel_id: str,
    user_id: str,
    message_text: str,
    parent_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
):
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    # If replying, validate parent exists and is same channel
    if parent_id is not None:
        parent = session.get(Message, parent_id)
        if parent is None or parent.channel_id != channel_id:
            raise ValueError("Parent message not found in this channel")

    # Generate Slack-style timestamp ID
    timestamp = time.time()
    message_id = f"{int(timestamp)}.{int((timestamp % 1) * 1_000_000):06d}"

    message = Message(
        message_id=message_id,
        channel_id=channel_id,
        user_id=user_id,
        message_text=message_text,
        parent_id=parent_id,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    session.add(message)
    return message


def send_direct_message(
    session: Session,
    message_text: str,
    sender_id: str,
    recipient_id: str,
    team_id: str | None = None,
    created_at: Optional[datetime] = None,
):
    sender = session.get(User, sender_id)
    recipient = session.get(User, recipient_id)
    if sender is None:
        raise ValueError("Sender not found")
    if recipient is None:
        raise ValueError("Recipient not found")

    dm_channel = find_or_create_dm_channel(
        session=session,
        user1_id=sender_id,
        user2_id=recipient_id,
        team_id=team_id if team_id is not None else "",
    )
    message = Message(
        channel_id=dm_channel.channel_id,
        user_id=sender_id,
        message_text=message_text,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    session.add(message)
    return message


# add-emoji-reaction


def add_emoji_reaction(
    session: Session,
    message_id: str,
    user_id: str,
    reaction_type: str,
    created_at: Optional[datetime] = None,
) -> MessageReaction:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError("Message not found")
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    existing = session.execute(
        select(MessageReaction)
        .where(MessageReaction.message_id == message_id)
        .where(MessageReaction.user_id == user_id)
        .where(MessageReaction.reaction_type == reaction_type)
    ).scalar_one_or_none()
    if existing:
        return existing
    reaction = MessageReaction(
        message_id=message_id,
        user_id=user_id,
        reaction_type=reaction_type,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    session.add(reaction)
    return reaction


# remove-emoji-reaction


def remove_emoji_reaction(session: Session, user_id: str, reaction_id: str):
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    reaction = session.get(MessageReaction, reaction_id)
    if reaction is None:
        raise ValueError("Reaction not found")
    if reaction.user_id != user_id:
        raise ValueError("User does not have this reaction")
    session.delete(reaction)
    return reaction


def update_message(session: Session, message_id: str, text: str) -> Message:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError("Message not found")
    message.message_text = text
    return message


def delete_message(session: Session, message_id: str) -> None:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError("Message not found")
    session.delete(message)


def get_reactions(session: Session, message_id: str) -> list[MessageReaction]:
    msg = session.get(Message, message_id)
    if msg is None:
        raise ValueError("Message not found")
    reactions = (
        session.execute(
            select(MessageReaction).where(MessageReaction.message_id == message_id)
        )
        .scalars()
        .all()
    )
    return list(reactions)


def get_user(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    return user


def get_user_by_email(session: Session, email: str) -> User:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")
    return user


def list_users(
    session: Session,
    team_id: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> list[User]:
    """List users with optional team filter and pagination."""
    query = select(User)
    if team_id is not None:
        query = (
            query.join(UserTeam)
            .where(UserTeam.team_id == team_id)
            .order_by(User.username.asc())
        )
    else:
        query = query.order_by(User.username.asc())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return list(session.execute(query).scalars().all())


def join_channel(
    session: Session,
    channel_id: str,
    user_id: str,
    joined_at: Optional[datetime] = None,
) -> ChannelMember:
    channel = session.get(Channel, channel_id)
    user = session.get(User, user_id)
    if channel is None or user is None:
        raise ValueError("Channel or user not found")
    existing = session.get(ChannelMember, (channel_id, user_id))
    if existing:
        return existing
    member = ChannelMember(
        channel_id=channel_id,
        user_id=user_id,
        **({"joined_at": joined_at} if joined_at is not None else {}),
    )
    session.add(member)
    return member


def leave_channel(session: Session, channel_id: str, user_id: str) -> None:
    member = session.get(ChannelMember, (channel_id, user_id))
    if member is None:
        raise ValueError("Not a channel member")
    session.delete(member)


def find_or_create_dm_channel(
    session: Session, user1_id: str, user2_id: str, team_id: str
) -> Channel:
    a, b = (user1_id, user2_id) if user1_id <= user2_id else (user2_id, user1_id)
    dm = (
        session.execute(
            select(Channel)
            .where(Channel.is_dm.is_(True), Channel.team_id == team_id)
            .where(
                and_(
                    exists().where(
                        and_(
                            ChannelMember.channel_id == Channel.channel_id,
                            ChannelMember.user_id == a,
                        )
                    ),
                    exists().where(
                        and_(
                            ChannelMember.channel_id == Channel.channel_id,
                            ChannelMember.user_id == b,
                        )
                    ),
                )
            )
        )
        .scalars()
        .first()
    )
    if dm:
        return dm
    ch = Channel(
        is_dm=True, is_private=True, team_id=team_id, channel_name=f"dm-{a}-{b}"
    )
    session.add(ch)
    session.add_all(
        [
            ChannelMember(channel_id=ch.channel_id, user_id=a),
            ChannelMember(channel_id=ch.channel_id, user_id=b),
        ]
    )
    return ch


# list-channels


def list_user_channels(
    session: Session,
    user_id: str,
    team_id: str,
    offset: int | None = None,
    limit: int | None = None,
):
    """List user channels with optional pagination.

    Args:
        session: Database session
        user_id: User ID
        team_id: Team ID
        offset: Number of rows to skip (for pagination)
        limit: Maximum number of rows to return (for pagination)

    Returns:
        List of channels the user is a member of
    """
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")

    query = (
        select(Channel)
        .where(Channel.team_id == team_id)
        .join(ChannelMember)
        .where(ChannelMember.user_id == user_id)
    )

    # Apply pagination if requested
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    channels = session.execute(query).scalars().all()
    return list(channels)


def list_public_channels(session: Session, team_id: str):
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    channels = (
        session.execute(select(Channel).where(Channel.team_id == team_id))
        .scalars()
        .all()
    )
    return channels


def list_direct_messages(session: Session, user_id: str, team_id: str):
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")
    direct_messages = (
        session.execute(
            select(Channel)
            .where(Channel.is_dm.is_(True), Channel.team_id == team_id)
            .join(ChannelMember)
            .where(ChannelMember.user_id == user_id)
        )
        .scalars()
        .all()
    )
    return direct_messages


# list-members-in-channel


def list_members_in_channel(
    session: Session,
    channel_id: str,
    team_id: str,
    offset: int | None = None,
    limit: int | None = None,
):
    """List members in a channel with optional pagination.

    Args:
        session: Database session
        channel_id: Channel ID
        team_id: Team ID (for validation)
        offset: Number of rows to skip (for pagination)
        limit: Maximum number of rows to return (for pagination)

    Returns:
        List of ChannelMember objects
    """
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    if channel.team_id != team_id:
        raise ValueError("Channel not in team")

    query = select(ChannelMember).where(ChannelMember.channel_id == channel_id)

    # Apply pagination if requested
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    members = session.execute(query).scalars().all()
    return members


# list-users-in-team


def list_users_in_team(session: Session, team_id: str, user_id: str):
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")
    users = (
        session.execute(select(User).join(UserTeam).where(UserTeam.team_id == team_id))
        .scalars()
        .all()
    )
    return users


# list-history (paginated)


def list_channel_history(
    session: Session,
    channel_id: str,
    user_id: str,
    team_id: str,
    limit: int,
    offset: int,
    oldest: datetime | None = None,
    latest: datetime | None = None,
    inclusive: bool = False,
):
    """List channel message history with optional timestamp filtering.

    Args:
        session: Database session
        channel_id: Channel ID
        user_id: User ID (for validation)
        team_id: Team ID (for validation)
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        oldest: Only include messages after this timestamp
        latest: Only include messages before this timestamp
        inclusive: If True, include messages with exact oldest/latest timestamps
    """
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")

    query = select(Message).where(Message.channel_id == channel_id)

    # Apply timestamp filters
    if oldest is not None:
        if inclusive:
            query = query.where(Message.created_at >= oldest)
        else:
            query = query.where(Message.created_at > oldest)

    if latest is not None:
        if inclusive:
            query = query.where(Message.created_at <= latest)
        else:
            query = query.where(Message.created_at < latest)

    query = query.order_by(Message.created_at.desc()).limit(limit).offset(offset)

    history = session.execute(query).scalars().all()
    return history
