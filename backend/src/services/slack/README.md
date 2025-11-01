# Supported Slack Methods

```python
SLACK_HANDLERS = {
    "chat.postMessage": chat_post_message,
    "chat.update": chat_update,
    "chat.delete": chat_delete,
    "conversations.create": conversations_create,
    "conversations.list": conversations_list,
    "conversations.history": conversations_history,
    "conversations.info": conversations_info,
    "conversations.join": conversations_join,
    "conversations.invite": conversations_invite,
    "conversations.open": conversations_open,
    "conversations.archive": conversations_archive,
    "conversations.unarchive": conversations_unarchive,
    "conversations.rename": conversations_rename,
    "conversations.setTopic": conversations_set_topic,
    "conversations.kick": conversations_kick,
    "conversations.leave": conversations_leave,
    "conversations.members": conversations_members,
    "reactions.add": reactions_add,
    "reactions.remove": reactions_remove,
    "reactions.get": reactions_get,
    "users.info": users_info,
    "users.list": users_list,
    "users.conversations": users_conversations,
    "search.messages": search_messages,
}
```
