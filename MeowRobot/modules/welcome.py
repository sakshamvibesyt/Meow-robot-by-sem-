#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
# This file is part of < https://github.com/TheAloneTeam/MeowRobot > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/MeowRobot/blob/master/LICENSE >
#
# All rights reserved.

import html
import random
import re
import time
import asyncio
from cachetools import TTLCache
from contextlib import suppress
from functools import partial

from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType, ParseMode, ChatMemberStatus
from telegram.error import BadRequest
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    filters,
    MessageHandler,
)
from telegram.helpers import escape_markdown, mention_html, mention_markdown

import MeowRobot
import MeowRobot.modules.sql.welcome_sql as sql
import MeowRobot.modules.sql.users_sql as user_sql
from MeowRobot import (
    DEMONS,
    DEV_USERS,
    DRAGONS,
    EVENT_LOGS,
    LOGGER,
    OWNER_ID,
    TIGERS,
    WOLVES,
    application,
)
from MeowRobot.modules.helper_funcs.chat_status import (
    is_user_ban_protected,
    user_admin,
)
from MeowRobot.modules.helper_funcs.misc import build_keyboard, revert_buttons
from MeowRobot.modules.helper_funcs.msg_types import get_welcome_type
from MeowRobot.modules.helper_funcs.string_handling import (
    escape_invalid_curly_brackets,
    markdown_parser,
)
from MeowRobot.modules.log_channel import loggable
from MeowRobot.modules.sql.global_bans_sql import is_user_gbanned
from MeowRobot.modules.users import USERS_GROUP

VALID_WELCOME_FORMATTERS = [
    "first",
    "last",
    "fullname",
    "username",
    "id",
    "count",
    "chatname",
    "mention",
]

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: "send_message",
    sql.Types.BUTTON_TEXT.value: "send_message",
    sql.Types.STICKER.value: "send_sticker",
    sql.Types.DOCUMENT.value: "send_document",
    sql.Types.PHOTO.value: "send_photo",
    sql.Types.AUDIO.value: "send_audio",
    sql.Types.VOICE.value: "send_voice",
    sql.Types.VIDEO.value: "send_video",
}

VERIFIED_USER_WAITLIST = {}
JOIN_CACHE = TTLCache(maxsize=1024, ttl=60)
LEFT_CACHE = TTLCache(maxsize=1024, ttl=60)


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE, message, keyboard, backup_message, msg=None):
    chat = update.effective_chat
    cleanserv = sql.clean_service(chat.id)
    reply = msg.message_id if msg else None
    if cleanserv and msg:
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except BadRequest:
            pass
        reply = None

    try:
        if msg:
            sent_msg = await msg.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                reply_to_message_id=reply,
            )
        else:
            sent_msg = await context.bot.send_message(
                chat.id,
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
    except BadRequest as excp:
        if excp.message in ("Reply message not found", "Message to be replied not found"):
            sent_msg = await context.bot.send_message(
                chat.id,
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        elif "Button_url_invalid" in excp.message or "wrong http url" in excp.message:
            text = markdown_parser(
                backup_message + "\nNote: the current message has an invalid url "
                "in one of its buttons. Please update."
            )
            if msg:
                sent_msg = await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_to_message_id=reply)
            else:
                sent_msg = await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            text = markdown_parser(
                backup_message + "\nNote: the current message has buttons which "
                "use url protocols that are unsupported by "
                "telegram. Please update."
            )
            if msg:
                sent_msg = await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_to_message_id=reply)
            else:
                sent_msg = await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            text = markdown_parser(
                backup_message + "\nNote: the current message has some bad urls. "
                "Please update."
            )
            if msg:
                sent_msg = await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_to_message_id=reply)
            else:
                sent_msg = await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
        elif excp.message in ("Have no rights to send a message", "Not enough rights to send text messages to the chat"):
            return None
        else:
            text = markdown_parser(
                backup_message + "\nNote: An error occurred when sending the "
                "custom message. Please update."
            )
            if msg:
                sent_msg = await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_to_message_id=reply)
            else:
                sent_msg = await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
    return sent_msg


async def deliver_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, new_mem, msg=None):
    bot, job_queue = context.bot, context.job_queue
    chat = update.effective_chat
    user = update.effective_user

    should_welc, cust_welcome, cust_content, welc_type = sql.get_welc_pref(chat.id)
    welc_mutes = sql.welcome_mutes(chat.id)
    human_checks = sql.get_human_checks(new_mem.id, chat.id)

    res = None
    sent = None
    should_mute = True
    welcome_bool = True
    media_wel = False

    if should_welc:
        reply = msg.message_id if msg else None
        cleanserv = sql.clean_service(chat.id)
        if cleanserv and msg:
            try:
                await bot.delete_message(chat.id, msg.message_id)
            except BadRequest:
                pass
            reply = None

        buttons = sql.get_welc_buttons(chat.id)
        keyb = build_keyboard(buttons)

        if welc_type not in (sql.Types.TEXT, sql.Types.BUTTON_TEXT):
            media_wel = True

        first_name = (
            new_mem.first_name or "PersonWithNoName"
        )

        if cust_welcome:
            if cust_welcome == sql.DEFAULT_WELCOME:
                cust_welcome = random.choice(
                    sql.DEFAULT_WELCOME_MESSAGES
                ).format(first=escape_markdown(first_name))

            if new_mem.last_name:
                fullname = escape_markdown(f"{first_name} {new_mem.last_name}")
            else:
                fullname = escape_markdown(first_name)
            count = await chat.get_member_count()
            mention = mention_markdown(new_mem.id, escape_markdown(first_name))
            if new_mem.username:
                username = "@" + escape_markdown(new_mem.username)
            else:
                username = mention

            valid_format = escape_invalid_curly_brackets(
                cust_welcome, VALID_WELCOME_FORMATTERS
            )
            res = valid_format.format(
                first=escape_markdown(first_name),
                last=escape_markdown(new_mem.last_name or first_name),
                fullname=escape_markdown(fullname),
                username=username,
                mention=mention,
                count=count,
                chatname=escape_markdown(chat.title),
                id=new_mem.id,
            )

        else:
            res = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(
                first=escape_markdown(first_name)
            )
            keyb = []

        backup_message = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(
            first=escape_markdown(first_name)
        )
        keyboard = InlineKeyboardMarkup(keyb)

    else:
        welcome_bool = False
        res = None
        keyboard = None
        backup_message = None
        reply = None

    if (
        await is_user_ban_protected(chat, new_mem.id, await chat.get_member(new_mem.id))
        or human_checks
    ):
        should_mute = False
    if new_mem.is_bot:
        should_mute = False

    if should_mute:
        if welc_mutes == "soft":
            await bot.restrict_chat_member(
                chat.id,
                new_mem.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_photos=False,
                    can_send_audios=False,
                    can_send_videos=False,
                    can_send_documents=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_other_messages=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_add_web_page_previews=False,
                ),
                until_date=(int(time.time() + 24 * 60 * 60)),
            )
        if welc_mutes == "strong":
            welcome_bool = False
            if not media_wel:
                VERIFIED_USER_WAITLIST.update(
                    {
                        new_mem.id: {
                            "should_welc": should_welc,
                            "media_wel": False,
                            "status": False,
                            "update": update,
                            "res": res,
                            "keyboard": keyboard,
                            "backup_message": backup_message,
                        }
                    }
                )
            else:
                VERIFIED_USER_WAITLIST.update(
                    {
                        new_mem.id: {
                            "should_welc": should_welc,
                            "chat_id": chat.id,
                            "status": False,
                            "media_wel": True,
                            "cust_content": cust_content,
                            "welc_type": welc_type,
                            "res": res,
                            "keyboard": keyboard,
                            "backup_message": backup_message,
                        }
                    }
                )
            new_join_mem = f'<a href="tg://user?id={new_mem.id}">{html.escape(new_mem.first_name)}</a>'
            text = f"{new_join_mem}, click the button below to prove you're human.\nYou have 120 seconds."
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Yes, I'm human.",
                            callback_data=f"user_join_({new_mem.id})",
                        )
                    ]
                ]
            )
            if msg:
                proof_msg = await msg.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=reply,
                )
            else:
                proof_msg = await bot.send_message(
                    chat.id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                )
            await bot.restrict_chat_member(
                chat.id,
                new_mem.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_send_photos=False,
                    can_send_audios=False,
                    can_send_videos=False,
                    can_send_documents=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ),
            )
            job_queue.run_once(
                check_not_bot,
                120,
                data={"member": new_mem, "chat_id": chat.id, "message_id": proof_msg.message_id},
                name="welcomemute",
            )

    if welcome_bool:
        if media_wel:
            method = getattr(bot, EN_FUNC := ENUM_FUNC_MAP[welc_type])
            try:
                sent = await method(
                    chat.id,
                    cust_content,
                    caption=res,
                    reply_markup=keyboard,
                    reply_to_message_id=reply,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as excp:
                if "wrong http url" in excp.message or "Button_url_invalid" in excp.message:
                    sent = await bot.send_message(
                        chat.id,
                        markdown_parser(
                            backup_message + "\nNote: the current message has an invalid url "
                            "in one of its buttons. Please update."
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_to_message_id=reply,
                    )
                elif excp.message in ("Reply message not found", "Message to be replied not found"):
                    sent = await method(
                        chat.id,
                        cust_content,
                        caption=res,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    sent = await bot.send_message(
                        chat.id,
                        markdown_parser(
                            backup_message + f"\nNote: An error occurred when sending the custom {EN_FUNC.split('_')[1]}. Please update."
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_to_message_id=reply,
                    )
        else:
            sent = await send(update, context, res, keyboard, backup_message, msg=msg)
        prev_welc = sql.get_clean_pref(chat.id)
        if prev_welc:
            try:
                await bot.delete_message(chat.id, prev_welc)
            except BadRequest:
                pass

            if sent:
                sql.set_clean_welcome(chat.id, sent.message_id)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE, new_mem, msg=None):
    bot = context.bot
    chat = update.effective_chat
    user = update.effective_user

    if new_mem.id == OWNER_ID:
        text = "Oh, Genos? Let's get this moving."
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"Bot Owner just joined the group"
        )

    elif new_mem.id in DEV_USERS:
        text = "Be cool! A member of the Heroes Association just joined."
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"Bot Dev just joined the group"
        )

    elif new_mem.id in DRAGONS:
        text = "Whoa! A Dragon disaster just joined! Stay Alert!"
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"Bot Sudo just joined the group"
        )

    elif new_mem.id in DEMONS:
        text = "Huh! Someone with a Demon disaster level just joined!"
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"Bot Support just joined the group"
        )

    elif new_mem.id in TIGERS:
        text = "Roar! A Tiger disaster just joined!"
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"A whitelisted user joined the chat"
        )

    elif new_mem.id in WOLVES:
        text = "Awoo! A Wolf disaster just joined!"
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"A whitelisted user joined the chat"
        )

    elif new_mem.id == bot.id:
        if not MeowRobot.ALLOW_CHATS:
            with suppress(BadRequest):
                text = f"Groups are disabled for {bot.first_name}, I'm outta here."
                if msg:
                    await msg.reply_text(text)
                else:
                    await bot.send_message(chat.id, text)
            await bot.leave_chat(chat.id)
            return ""
        try:
            await bot.send_message(
                EVENT_LOGS,
                "#NEW_GROUP\n<b>Group name:</b> {}\n<b>ID:</b> <code>{}</code>\nAdded by : {} | <code>{}</code>".format(
                    html.escape(chat.title),
                    chat.id,
                    user.first_name if user else "Unknown",
                    user.id if user else "Unknown",
                ),
                parse_mode=ParseMode.HTML,
            )
        except BadRequest as exc:
            LOGGER.warning("Could not send new-group log to EVENT_LOGS (%s): %s", EVENT_LOGS, exc)
        except Exception as exc:
            # A logging failure must not prevent the bot from welcoming itself
            # or completing the new-group update.
            LOGGER.warning("Could not send new-group log to EVENT_LOGS (%s): %s", EVENT_LOGS, exc)
        text = "Watashi ga kita !"
        if msg:
            await msg.reply_text(text)
        else:
            await bot.send_message(chat.id, text)
        return ""

    if not new_mem.is_bot:
        user_sql.update_user(new_mem.id, new_mem.username, chat.id, chat.title)
        await deliver_welcome(update, context, new_mem, msg)

    return (
        f"{html.escape(chat.title)}\n"
        f"#USER_JOINED\n"
        f"<b>User</b>: {mention_html(new_mem.id, new_mem.first_name)}\n"
        f"<b>ID</b>: <code>{new_mem.id}</code>"
    )


@loggable
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not msg or not msg.new_chat_members:
        return ""

    log = ""
    for new_mem in msg.new_chat_members:
        if JOIN_CACHE.get((update.effective_chat.id, new_mem.id)):
            continue
        JOIN_CACHE[(update.effective_chat.id, new_mem.id)] = True
        log += await handle_new_member(update, context, new_mem, msg)
    return log


async def check_not_bot(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    data = context.job.data
    member = data['member']
    chat_id = data['chat_id']
    message_id = data['message_id']

    member_dict = VERIFIED_USER_WAITLIST.pop(member.id, None)
    if member_dict:
        member_status = member_dict.get("status")
        if not member_status:
            try:
                await bot.ban_chat_member(chat_id, member.id)
                await bot.unban_chat_member(chat_id, member.id)
            except:
                pass

            try:
                await bot.edit_message_text(
                    "*kicks user*\nThey can always rejoin and try.",
                    chat_id=chat_id,
                    message_id=message_id,
                )
            except:
                pass


async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE, left_mem, msg=None):
    bot = context.bot
    chat = update.effective_chat

    user_sql.update_user(left_mem.id, left_mem.username, chat.id, chat.title)

    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)

    if left_mem.id == bot.id:
        return ""

    if should_goodbye:
        reply = msg.message_id if msg else None
        cleanserv = sql.clean_service(chat.id)
        if cleanserv and msg:
            try:
                await bot.delete_message(chat.id, msg.message_id)
            except BadRequest:
                pass
            reply = None

        if is_user_gbanned(left_mem.id):
            return ""

        if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
            method = getattr(bot, ENUM_FUNC_MAP[goodbye_type])
            try:
                await method(chat.id, cust_goodbye)
            except BadRequest:
                pass
            return ""

        first_name = (
            left_mem.first_name or "PersonWithNoName"
        )
        if cust_goodbye:
            if cust_goodbye == sql.DEFAULT_GOODBYE:
                cust_goodbye = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(
                    first=escape_markdown(first_name)
                )
            if left_mem.last_name:
                fullname = escape_markdown(f"{first_name} {left_mem.last_name}")
            else:
                fullname = escape_markdown(first_name)
            count = await chat.get_member_count()
            mention = mention_markdown(left_mem.id, first_name)
            if left_mem.username:
                username = "@" + escape_markdown(left_mem.username)
            else:
                username = mention

            valid_format = escape_invalid_curly_brackets(
                cust_goodbye, VALID_WELCOME_FORMATTERS
            )
            res = valid_format.format(
                first=escape_markdown(first_name),
                last=escape_markdown(left_mem.last_name or first_name),
                fullname=escape_markdown(fullname),
                username=username,
                mention=mention,
                count=count,
                chatname=escape_markdown(chat.title),
                id=left_mem.id,
            )
            buttons = sql.get_gdbye_buttons(chat.id)
            keyb = build_keyboard(buttons)

        else:
            res = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(
                first=first_name
            )
            keyb = []

        keyboard = InlineKeyboardMarkup(keyb)

        await send(
            update,
            context,
            res,
            keyboard,
            random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(first=first_name),
            msg=msg
        )
    return ""


@loggable
async def left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.left_chat_member:
        return ""

    if LEFT_CACHE.get((update.effective_chat.id, msg.left_chat_member.id)):
        return ""
    LEFT_CACHE[(update.effective_chat.id, msg.left_chat_member.id)] = True
    return await handle_left_member(update, context, msg.left_chat_member, msg)


@loggable
async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return ""

    chat = update.effective_chat
    user = update.effective_user

    # We want the person whose status changed
    target_user = result.new_chat_member.user

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    if old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) and new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        # User joined
        if JOIN_CACHE.get((chat.id, target_user.id)):
            return ""
        JOIN_CACHE[(chat.id, target_user.id)] = True
        return await handle_new_member(update, context, target_user)
    elif old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER) and new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        # User left
        if LEFT_CACHE.get((chat.id, target_user.id)):
            return ""
        LEFT_CACHE[(chat.id, target_user.id)] = True
        return await handle_left_member(update, context, target_user)

    return ""


@user_admin
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat = update.effective_chat
    if not args or args[0].lower() == "noformat":
        noformat = True if args and args[0].lower() == "noformat" else False
        pref, welcome_m, cust_content, welcome_type = sql.get_welc_pref(chat.id)
        await update.effective_message.reply_text(
            f"This chat has it's welcome setting set to: `{pref}`.\n"
            f"*The welcome message (not filling the {{}}) is:*",
            parse_mode=ParseMode.MARKDOWN,
        )

        if welcome_type == sql.Types.BUTTON_TEXT or welcome_type == sql.Types.TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                await update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                await send(update, context, welcome_m, keyboard, sql.DEFAULT_WELCOME, msg=update.effective_message)
        else:
            buttons = sql.get_welc_buttons(chat.id)
            method = getattr(context.bot, EN_FUNC := ENUM_FUNC_MAP[welcome_type])
            if noformat:
                welcome_m += revert_buttons(buttons)
                try:
                    await method(chat.id, cust_content, caption=welcome_m)
                except BadRequest:
                    await update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)
                try:
                    await method(
                        chat.id,
                        cust_content,
                        caption=welcome_m,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except BadRequest as excp:
                    if "wrong http url" in excp.message or "Button_url_invalid" in excp.message:
                        await update.effective_message.reply_text(
                            markdown_parser(
                                sql.DEFAULT_WELCOME + "\nNote: the current message has an invalid url "
                                "in one of its buttons. Please update."
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    else:
                        await update.effective_message.reply_text(
                            markdown_parser(
                                sql.DEFAULT_WELCOME + f"\nNote: An error occurred when sending the custom {EN_FUNC.split('_')[1]}. Please update."
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                        )

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            await update.effective_message.reply_text(
                "Okay! I'll greet members when they join."
            )

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            await update.effective_message.reply_text(
                "I'll go loaf around and not welcome anyone then."
            )

        else:
            await update.effective_message.reply_text(
                "I understand 'on/yes' or 'off/no' only!"
            )


@user_admin
async def goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat = update.effective_chat

    if not args or args[0] == "noformat":
        noformat = True if args and args[0].lower() == "noformat" else False
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        await update.effective_message.reply_text(
            f"This chat has it's goodbye setting set to: `{pref}`.\n"
            f"*The goodbye  message (not filling the {{}}) is:*",
            parse_mode=ParseMode.MARKDOWN,
        )

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                await update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                await send(update, context, goodbye_m, keyboard, sql.DEFAULT_GOODBYE, msg=update.effective_message)

        else:
            method = getattr(context.bot, EN_FUNC := ENUM_FUNC_MAP[goodbye_type])
            if noformat:
                try:
                    await method(chat.id, goodbye_m)
                except BadRequest:
                    await update.effective_message.reply_text(goodbye_m)

            else:
                try:
                    await method(
                        chat.id, goodbye_m, parse_mode=ParseMode.MARKDOWN
                    )
                except BadRequest:
                    await update.effective_message.reply_text(
                        goodbye_m, parse_mode=ParseMode.MARKDOWN
                    )

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            await update.effective_message.reply_text("Ok!")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            await update.effective_message.reply_text("Ok!")

        else:
            await update.effective_message.reply_text(
                "I understand 'on/yes' or 'off/no' only!"
            )


@user_admin
@loggable
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    text, data_type, content, buttons = await get_welcome_type(msg)

    if data_type is None:
        await msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_welcome(chat.id, content, text, data_type, buttons)
    await msg.reply_text("Successfully set custom welcome message!")

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#SET_WELCOME\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Set the welcome message."
    )


@user_admin
@loggable
async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_welcome(chat.id, None, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    await update.effective_message.reply_text(
        "Successfully reset welcome message to default!"
    )

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#RESET_WELCOME\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Reset the welcome message to default."
    )


@user_admin
@loggable
async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    text, data_type, content, buttons = await get_welcome_type(msg)

    if data_type is None:
        await msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_gdbye(chat.id, content or text, data_type, buttons)
    await msg.reply_text("Successfully set custom goodbye message!")
    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#SET_GOODBYE\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Set the goodbye message."
    )


@user_admin
@loggable
async def reset_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    await update.effective_message.reply_text(
        "Successfully reset goodbye message to default!"
    )

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#RESET_GOODBYE\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Reset the goodbye message."
    )


@user_admin
@loggable
async def welcomemute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if len(args) >= 1:
        if args[0].lower() in ("off", "no"):
            sql.set_welcome_mutes(chat.id, False)
            await msg.reply_text("I will no longer mute people on joining!")
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>OFF</b>."
            )
        elif args[0].lower() in ["soft"]:
            sql.set_welcome_mutes(chat.id, "soft")
            await msg.reply_text(
                "I will restrict users' permission to send media for 24 hours."
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>SOFT</b>."
            )
        elif args[0].lower() in ["strong"]:
            sql.set_welcome_mutes(chat.id, "strong")
            await msg.reply_text(
                "I will now mute people when they join until they prove they're not a bot.\nThey will have 120seconds before they get kicked."
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>STRONG</b>."
            )
        else:
            await msg.reply_text(
                "Please enter <code>off</code>/<code>no</code>/<code>soft</code>/<code>strong</code>!",
                parse_mode=ParseMode.HTML,
            )
            return ""
    else:
        curr_setting = sql.welcome_mutes(chat.id)
        reply = (
            f"\n Give me a setting!\nChoose one out of: <code>off</code>/<code>no</code> or <code>soft</code> or <code>strong</code> only! \n"
            f"Current setting: <code>{curr_setting}</code>"
        )
        await msg.reply_text(reply, parse_mode=ParseMode.HTML)
        return ""


@user_admin
@loggable
async def clean_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            await update.effective_message.reply_text(
                "I should be deleting welcome messages up to two days old."
            )
        else:
            await update.effective_message.reply_text(
                "I'm currently not deleting old welcome messages!"
            )
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_clean_welcome(str(chat.id), True)
        await update.effective_message.reply_text("I'll try to delete old welcome messages!")
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#CLEAN_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Has toggled clean welcomes to <code>ON</code>."
        )
    elif args[0].lower() in ("off", "no"):
        sql.set_clean_welcome(str(chat.id), False)
        await update.effective_message.reply_text("I won't delete old welcome messages.")
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#CLEAN_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Has toggled clean welcomes to <code>OFF</code>."
        )
    else:
        await update.effective_message.reply_text("I understand 'on/yes' or 'off/no' only!")
        return ""


@user_admin
async def cleanservice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    if chat.type != ChatType.PRIVATE:
        if len(args) >= 1:
            var = args[0]
            if var in ("no", "off"):
                sql.set_clean_service(chat.id, False)
                await update.effective_message.reply_text("Welcome clean service is : off")
            elif var in ("yes", "on"):
                sql.set_clean_service(chat.id, True)
                await update.effective_message.reply_text("Welcome clean service is : on")
            else:
                await update.effective_message.reply_text(
                    "Invalid option", parse_mode=ParseMode.HTML
                )
        else:
            await update.effective_message.reply_text(
                "Usage is <code>on</code>/<code>yes</code> or <code>off</code>/<code>no</code>",
                parse_mode=ParseMode.HTML,
            )
    else:
        curr = sql.clean_service(chat.id)
        if curr:
            await update.effective_message.reply_text(
                "Welcome clean service is : <code>on</code>", parse_mode=ParseMode.HTML
            )
        else:
            await update.effective_message.reply_text(
                "Welcome clean service is : <code>off</code>", parse_mode=ParseMode.HTML
            )


async def user_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    query = update.callback_query
    bot = context.bot
    match = re.match(r"user_join_\((.+?)\)", query.data)
    message = update.effective_message
    join_user = int(match.group(1))

    if join_user == user.id:
        sql.set_human_checks(user.id, chat.id)
        member_dict = VERIFIED_USER_WAITLIST.pop(user.id, None)
        if member_dict:
            member_dict["status"] = True
            VERIFIED_USER_WAITLIST.update({user.id: member_dict})
            await query.answer(text="Yeet! You're a human, unmuted!")
            await bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                    can_send_polls=True,
                    can_change_info=True,
                    can_send_photos=True,
                    can_send_audios=True,
                    can_send_videos=True,
                    can_send_documents=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            try:
                await bot.delete_message(chat.id, message.message_id)
            except:
                pass
            if member_dict["should_welc"]:
                if member_dict["media_wel"]:
                    method = getattr(bot, EN_FUNC := ENUM_FUNC_MAP[member_dict["welc_type"]])
                    try:
                        sent = await method(
                            member_dict["chat_id"],
                            member_dict["cust_content"],
                            caption=member_dict["res"],
                            reply_markup=member_dict["keyboard"],
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except BadRequest as excp:
                        if "wrong http url" in excp.message or "Button_url_invalid" in excp.message:
                            sent = await bot.send_message(
                                member_dict["chat_id"],
                                markdown_parser(
                                    member_dict["backup_message"] + "\nNote: the current message has an invalid url "
                                    "in one of its buttons. Please update."
                                ),
                                parse_mode=ParseMode.MARKDOWN,
                            )
                        else:
                            sent = await bot.send_message(
                                member_dict["chat_id"],
                                markdown_parser(
                                    member_dict["backup_message"] + f"\nNote: An error occurred when sending the custom {EN_FUNC.split('_')[1]}. Please update."
                                ),
                                parse_mode=ParseMode.MARKDOWN,
                            )
                else:
                    sent = await send(
                        member_dict["update"],
                        context,
                        member_dict["res"],
                        member_dict["keyboard"],
                        member_dict["backup_message"],
                    )

                prev_welc = sql.get_clean_pref(chat.id)
                if prev_welc:
                    try:
                        await bot.delete_message(chat.id, prev_welc)
                    except BadRequest:
                        pass

                    if sent:
                        sql.set_clean_welcome(chat.id, sent.message_id)

    else:
        await query.answer(text="You're not allowed to do this!", show_alert=True)


WELC_HELP_TXT = (
    "Your group's welcome/goodbye messages can be personalised in multiple ways. If you want the messages"
    " to be individually generated, like the default welcome message is, you can use *these* variables:\n"
    " • `{{first}}`*:* this represents the user's *first* name\n"
    " • `{{last}}`*:* this represents the user's *last* name. Defaults to *first name* if user has no "
    "last name.\n"
    " • `{{fullname}}`*:* this represents the user's *full* name. Defaults to *first name* if user has no "
    "last name.\n"
    " • `{{username}}`*:* this represents the user's *username*. Defaults to a *mention* of the user's "
    "first name if has no username.\n"
    " • `{{mention}}`*:* this simply *mentions* a user - tagging them with their first name.\n"
    " • `{{id}}`*:* this represents the user's *id*\n"
    " • `{{count}}`*:* this represents the user's *member number*.\n"
    " • `{{chatname}}`*:* this represents the *current chat name*.\n"
    "\nEach variable MUST be surrounded by `{{}}` to be replaced.\n"
    "Welcome messages also support markdown, so you can make any elements bold/italic/code/links. "
    "Buttons are also supported, so you can make your welcomes look awesome with some nice intro "
    "buttons.\n"
    "To create a button linking to your rules, use this: `[Rules](buttonurl://t.me/{username}?start=group_id)`. "
    "Simply replace `group_id` with your group's id, which can be obtained via /id, and you're good to "
    "go. Note that group ids are usually preceded by a `-` sign; this is required, so please don't "
    "remove it.\n"
    "You can even set images/gifs/videos/voice messages as the welcome message by "
    "replying to the desired media, and calling `/setwelcome`."
)

WELC_MUTE_HELP_TXT = (
    "You can get the bot to mute new people who join your group and hence prevent spambots from flooding your group. "
    "The following options are possible:\n"
    "• `/welcomemute soft`*:* restricts new members from sending media for 24 hours.\n"
    "• `/welcomemute strong`*:* mutes new members till they tap on a button thereby verifying they're human.\n"
    "• `/welcomemute off`*:* turns off welcomemute.\n"
    "*Note:* Strong mode kicks a user from the chat if they dont verify in 120seconds. They can always rejoin though"
)


async def welcome_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        WELC_HELP_TXT.format(username=context.bot.username),
        parse_mode=ParseMode.MARKDOWN,
    )


async def welcome_mute_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        WELC_MUTE_HELP_TXT, parse_mode=ParseMode.MARKDOWN
    )


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


async def __chat_settings__(chat_id, user_id):
    welcome_pref = sql.get_welc_pref(chat_id)[0]
    goodbye_pref = sql.get_gdbye_pref(chat_id)[0]
    return (
        "This chat has it's welcome preference set to `{}`.\n"
        "It's goodbye preference is `{}`.".format(welcome_pref, goodbye_pref)
    )


__help__ = """
*Admins only:*
 ❍ /welcome <on/off>*:* Toggle welcomes.
 ❍ /welcome*:* Show current settings.
 ❍ /goodbye <on/off>*:* Toggle goodbye.
 ❍ /goodbye*:* Show current settings.
 ❍ /setwelcome <text>*:* Set custom welcome message.
 ❍ /setgoodbye <text>*:* Set custom goodbye message.
 ❍ /resetwelcome*:* Reset to default welcome.
 ❍ /resetgoodbye*:* Reset to default goodbye.
 ❍ /cleanwelcome <on/off>*:* Delete previous welcome message on join.
 ❍ /welcomemutehelp*:* Info about welcome mutes.
 ❍ /cleanservice <on/off>*:* Delete telegram service messages.
 ❍ /welcomehelp*:* Formatting info for welcome/goodbye.
"""

NEW_MEM_HANDLER = MessageHandler(
    filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member
)
LEFT_MEM_HANDLER = MessageHandler(
    filters.StatusUpdate.LEFT_CHAT_MEMBER, left_member
)
WELC_PREF_HANDLER = CommandHandler(
    "welcome", welcome, filters=filters.ChatType.GROUPS
)
GOODBYE_PREF_HANDLER = CommandHandler(
    "goodbye", goodbye, filters=filters.ChatType.GROUPS
)
SET_WELCOME = CommandHandler(
    "setwelcome", set_welcome, filters=filters.ChatType.GROUPS
)
SET_GOODBYE = CommandHandler(
    "setgoodbye", set_goodbye, filters=filters.ChatType.GROUPS
)
RESET_WELCOME = CommandHandler(
    "resetwelcome", reset_welcome, filters=filters.ChatType.GROUPS
)
RESET_GOODBYE = CommandHandler(
    "resetgoodbye", reset_goodbye, filters=filters.ChatType.GROUPS
)
WELCOMEMUTE_HANDLER = CommandHandler(
    "welcomemute", welcomemute, filters=filters.ChatType.GROUPS
)
CLEAN_SERVICE_HANDLER = CommandHandler(
    "cleanservice", cleanservice, filters=filters.ChatType.GROUPS
)
CLEAN_WELCOME = CommandHandler(
    "cleanwelcome", clean_welcome, filters=filters.ChatType.GROUPS
)
WELCOME_HELP = CommandHandler("welcomehelp", welcome_help)
WELCOME_MUTE_HELP = CommandHandler("welcomemutehelp", welcome_mute_help)
BUTTON_VERIFY_HANDLER = CallbackQueryHandler(
    user_button, pattern=r"user_join_"
)
CHAT_MEMBER_HANDLER = ChatMemberHandler(
    chat_member_update, ChatMemberHandler.CHAT_MEMBER
)

application.add_handler(NEW_MEM_HANDLER)
application.add_handler(LEFT_MEM_HANDLER)
application.add_handler(WELC_PREF_HANDLER)
application.add_handler(GOODBYE_PREF_HANDLER)
application.add_handler(SET_WELCOME)
application.add_handler(SET_GOODBYE)
application.add_handler(RESET_WELCOME)
application.add_handler(RESET_GOODBYE)
application.add_handler(CLEAN_WELCOME)
application.add_handler(WELCOME_HELP)
application.add_handler(WELCOMEMUTE_HANDLER)
application.add_handler(CLEAN_SERVICE_HANDLER)
application.add_handler(BUTTON_VERIFY_HANDLER)
application.add_handler(WELCOME_MUTE_HELP)
application.add_handler(CHAT_MEMBER_HANDLER)

__mod_name__ = "Wᴇʟᴄᴏᴍᴇ"
__command_list__ = []
__handlers__ = [
    NEW_MEM_HANDLER,
    LEFT_MEM_HANDLER,
    WELC_PREF_HANDLER,
    GOODBYE_PREF_HANDLER,
    SET_WELCOME,
    SET_GOODBYE,
    RESET_WELCOME,
    RESET_GOODBYE,
    CLEAN_WELCOME,
    WELCOME_HELP,
    WELCOMEMUTE_HANDLER,
    CLEAN_SERVICE_HANDLER,
    BUTTON_VERIFY_HANDLER,
    WELCOME_MUTE_HELP,
    CHAT_MEMBER_HANDLER,
]
