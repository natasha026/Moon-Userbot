#  Moon-Userbot - telegram userbot
#  Copyright (C) 2020-present Moon Userbot Organization

from pyrogram import Client, ContinuePropagation, errors, filters
from pyrogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from utils.db import db
from utils.misc import modules_help, prefix
from utils.scripts import format_exc
import re


def get_filters_chat(chat_id):
    return db.get("core.filters", f"{chat_id}", {})


def set_filters_chat(chat_id, filters_):
    return db.set("core.filters", f"{chat_id}", filters_)


# Whole-word regex match (case-insensitive)
async def contains_filter(_, __, m):
    if not m.text:
        return False
    text = m.text.lower()
    filters_dict = get_filters_chat(m.chat.id)
    return any(re.search(fr'\b{re.escape(k)}\b', text) for k in filters_dict)


contains = filters.create(contains_filter)


@Client.on_message(contains)
async def filters_main_handler(client: Client, message: Message):
    chat_filters = get_filters_chat(message.chat.id)
    text = message.text.lower()

    matched_key = next((k for k in chat_filters if re.search(fr'\b{re.escape(k)}\b', text)), None)

    if matched_key is None:
        raise ContinuePropagation

    value = chat_filters[matched_key]
    try:
        await client.get_messages(int(value["CHAT_ID"]), int(value["MESSAGE_ID"]))
    except errors.RPCError as exc:
        raise ContinuePropagation from exc

    if value.get("MEDIA_GROUP"):
        messages_grouped = await client.get_media_group(
            int(value["CHAT_ID"]), int(value["MESSAGE_ID"])
        )
        media_grouped_list = []
        for _ in messages_grouped:
            if _.photo:
                media_grouped_list.append(InputMediaPhoto(_.photo.file_id, _.caption.HTML) if _.caption else InputMediaPhoto(_.photo.file_id))
            elif _.video:
                media_grouped_list.append(InputMediaVideo(_.video.file_id, _.caption.HTML) if _.caption else InputMediaVideo(_.video.file_id))
            elif _.audio:
                media_grouped_list.append(InputMediaAudio(_.audio.file_id, _.caption.HTML) if _.caption else InputMediaAudio(_.audio.file_id))
            elif _.document:
                media_grouped_list.append(InputMediaDocument(_.document.file_id, _.caption.HTML) if _.caption else InputMediaDocument(_.document.file_id))
        await client.send_media_group(
            message.chat.id, media_grouped_list, reply_to_message_id=message.id
        )
    else:
        await client.copy_message(
            message.chat.id,
            int(value["CHAT_ID"]),
            int(value["MESSAGE_ID"]),
            reply_to_message_id=message.id,
        )
    raise ContinuePropagation


@Client.on_message(filters.command(["filter"], prefix) & filters.me)
async def filter_handler(client: Client, message: Message):
    try:
        if len(message.text.split()) < 2:
            return await message.edit(f"<b>Usage</b>: <code>{prefix}filter [name] (Reply required)</code>")
        name = message.text.split(maxsplit=1)[1].lower()
        chat_filters = get_filters_chat(message.chat.id)
        if name in chat_filters:
            return await message.edit(f"<b>Filter</b> <code>{name}</code> already exists.")
        if not message.reply_to_message:
            return await message.edit("<b>Reply to message</b> please.")

        try:
            chat = await client.get_chat(db.get("core.notes", "chat_id", 0))
        except (errors.RPCError, ValueError, KeyError):
            chat = await client.create_supergroup("Moon_Userbot_Notes_Filters", "Don't touch this group, please")
            db.set("core.notes", "chat_id", chat.id)

        chat_id = chat.id

        if message.reply_to_message.media_group_id:
            get_media_group = [
                _.id for _ in await client.get_media_group(
                    message.chat.id, message.reply_to_message.id
                )
            ]
            try:
                message_id = await client.forward_messages(chat_id, message.chat.id, get_media_group)
            except errors.ChatForwardsRestricted:
                await message.edit("<b>Forwarding messages is restricted by chat admins</b>")
                return
            filter_ = {
                "MESSAGE_ID": str(message_id[1].id),
                "MEDIA_GROUP": True,
                "CHAT_ID": str(chat_id),
            }
        else:
            try:
                message_id = await message.reply_to_message.forward(chat_id)
            except errors.ChatForwardsRestricted:
                message_id = await message.copy(chat_id)
            filter_ = {
                "MEDIA_GROUP": False,
                "MESSAGE_ID": str(message_id.id),
                "CHAT_ID": str(chat_id),
            }

        chat_filters.update({name: filter_})
        set_filters_chat(message.chat.id, chat_filters)
        return await message.edit(f"<b>Filter</b> <code>{name}</code> has been added.")
    except Exception as e:
        return await message.edit(format_exc(e))


@Client.on_message(filters.command(["filters"], prefix) & filters.me)
async def filters_handler(_, message: Message):
    try:
        text = ""
        for index, (key, _) in enumerate(get_filters_chat(message.chat.id).items(), start=1):
            key = key.replace("<", "").replace(">", "")
            text += f"{index}. <code>{key}</code>\n"
        text = f"<b>Your filters in current chat</b>:\n\n{text}"
        return await message.edit(text[:4096])
    except Exception as e:
        return await message.edit(format_exc(e))


@Client.on_message(filters.command(["delfilter", "filterdel", "fdel"], prefix) & filters.me)
async def filter_del_handler(_, message: Message):
    try:
        if len(message.text.split()) < 2:
            return await message.edit(f"<b>Usage</b>: <code>{prefix}fdel [name]</code>")
        name = message.text.split(maxsplit=1)[1].lower()
        chat_filters = get_filters_chat(message.chat.id)
        if name not in chat_filters:
            return await message.edit(f"<b>Filter</b> <code>{name}</code> doesn't exist.")
        del chat_filters[name]
        set_filters_chat(message.chat.id, chat_filters)
        return await message.edit(f"<b>Filter</b> <code>{name}</code> has been deleted.")
    except Exception as e:
        return await message.edit(format_exc(e))


@Client.on_message(filters.command(["fsearch"], prefix) & filters.me)
async def filter_search_handler(_, message: Message):
    try:
        if len(message.text.split()) < 2:
            return await message.edit(f"<b>Usage</b>: <code>{prefix}fsearch [name]</code>")
        name = message.text.split(maxsplit=1)[1].lower()
        chat_filters = get_filters_chat(message.chat.id)
        if name not in chat_filters:
            return await message.edit(f"<b>Filter</b> <code>{name}</code> doesn't exist.")
        return await message.edit(
            f"<b>Trigger</b>:\n<code>{name}</code>\n<b>Answer</b>:\n{chat_filters[name]}"
        )
    except Exception as e:
        return await message.edit(format_exc(e))


modules_help["filters"] = {
    "filter [name]": "Create filter (Reply required)",
    "filters": "List of all triggers",
    "fdel [name]": "Delete filter by name",
    "fsearch [name]": "Info filter by name",
}
