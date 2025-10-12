from backend.src.services.slack.database.schema import (
    User,
    Team,
    Channel,
    Message,
    ChannelMember,
    MessageReaction,
    UserTeam,
)

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, exists, and_
# Create Team


def create_team(
    session: Session,
    team_name: str,
    created_at: Optional[datetime] = None,
    default_channel_name: str | None = None,
):
    team = Team(team_name=team_name)
    if created_at is not None:
        team.created_at = created_at
    session.add(team)
    session.flush()
    if default_channel_name:
        channel = Channel(
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
    created_at: Optional[datetime] = None,
    real_name: str | None = None,
    display_name: str | None = None,
    timezone: str | None = None,
    title: str | None = None,
):
    user = User(
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
    team_id: int,
    created_at: Optional[datetime] = None,
) -> Channel:
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")

    channel = Channel(
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


def archive_channel(session: Session, channel_id: int):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.is_archived = True
    return channel


# unarchive-channel


def unarchive_channel(session: Session, channel_id: int):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.is_archived = False
    return channel


# rename-channel


def rename_channel(session: Session, channel_id: int, new_name: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.channel_name = new_name
    return channel


# set-channel-topic


def set_channel_topic(session: Session, channel_id: int, topic: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    channel.topic_text = topic
    return channel


# invite-user-to-channel


def invite_user_to_channel(
    session: Session,
    channel_id: int,
    user_id: int,
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


def kick_user_from_channel(session: Session, channel_id: int, user_id: int):
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
    channel_id: int,
    user_id: int,
    message_text: str,
    parent_id: Optional[int] = None,
    created_at: Optional[datetime] = None,
):
    channel = session.get(Channel, channel_id)
    user = session.get(User, user_id)
    if channel is None or user is None:
        raise ValueError("Channel or user not found")
    # If replying, validate parent exists and is same channel
    if parent_id is not None:
        parent = session.get(Message, parent_id)
        if parent is None or parent.channel_id != channel_id:
            raise ValueError("Parent message not found in this channel")
    message = Message(
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
    user_id: int,
    message_text: str,
    sender_id: int,
    recipient_id: int,
    team_id: int | None = None,
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
        team_id=team_id if team_id is not None else 0,
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
    message_id: int,
    user_id: int,
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


def remove_emoji_reaction(session: Session, user_id: int, reaction_id: int):
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


def update_message(session: Session, message_id: int, text: str) -> Message:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError("Message not found")
    message.message_text = text
    return message


def delete_message(session: Session, message_id: int) -> None:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError("Message not found")
    session.delete(message)


def get_reactions(session: Session, message_id: int) -> list[MessageReaction]:
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


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    return user


def get_user_by_email(session: Session, email: str) -> User:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")
    return user


def list_users(session: Session, team_id: int | None = None) -> list[User]:
    query = select(User)
    if team_id is not None:
        query = (
            query.join(UserTeam)
            .where(UserTeam.team_id == team_id)
            .order_by(User.username.asc())
        )
    else:
        query = query.order_by(User.username.asc())
    return list(session.execute(query).scalars().all())


def join_channel(
    session: Session,
    channel_id: int,
    user_id: int,
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


def leave_channel(session: Session, channel_id: int, user_id: int) -> None:
    member = session.get(ChannelMember, (channel_id, user_id))
    if member is None:
        raise ValueError("Not a channel member")
    session.delete(member)


def find_or_create_dm_channel(
    session: Session, user1_id: int, user2_id: int, team_id: int
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
    session.flush()
    session.add_all(
        [
            ChannelMember(channel_id=ch.channel_id, user_id=a),
            ChannelMember(channel_id=ch.channel_id, user_id=b),
        ]
    )
    return ch


# list-channels


def list_user_channels(session: Session, user_id: int, team_id: int):
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")

    channels = (
        session.execute(
            select(Channel)
            .where(Channel.team_id == team_id)
            .join(ChannelMember)
            .where(ChannelMember.user_id == user_id)
        )
        .scalars()
        .all()
    )
    return channels


def list_public_channels(session: Session, team_id: int):
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    channels = (
        session.execute(select(Channel).where(Channel.team_id == team_id))
        .scalars()
        .all()
    )
    return channels


def list_direct_messages(session: Session, user_id: int, team_id: int):
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


def list_members_in_channel(session: Session, channel_id: int, team_id: int):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    if channel.team_id != team_id:
        raise ValueError("Channel not in team")
    members = (
        session.execute(
            select(ChannelMember).where(ChannelMember.channel_id == channel_id)
        )
        .scalars()
        .all()
    )
    return members


# list-users-in-team


def list_users_in_team(session: Session, team_id: int, user_id: int):
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
    channel_id: int,
    user_id: int,
    team_id: int,
    limit: int,
    offset: int,
):
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ValueError("Channel not found")
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    team_member = session.get(UserTeam, (user_id, team_id))
    if team_member is None:
        raise ValueError("User is not a member of the team")
    history = (
        session.execute(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return history
