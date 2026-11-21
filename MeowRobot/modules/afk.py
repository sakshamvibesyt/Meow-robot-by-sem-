#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
# This file is part of < https://github.com/TheAloneTeam/MeowRobot > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/MeowRobot/blob/master/LICENSE >
#
# All rights reserved.

import html
import random

from telegram import Update
from telegram.constants import ChatType, MessageEntityType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, filters, MessageHandler

from MeowRobot import application
from MeowRobot.modules.disable import (
    DisableAbleCommandHandler,
    DisableAbleMessageHandler,
)
from MeowRobot.modules.sql import afk_sql as sql
from MeowRobot.modules.users import get_user_id

AFK_GROUP = 7
AFK_REPLY_GROUP = 8


async def afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.effective_message.text.split(None, 1)
    user = update.effective_user

    if not user:
        return

    if user.id in [777000, 1087968824]:
        return

    notice = ""
    if len(args) >= 2:
        reason = args[1]
        if len(reason) > 100:
            reason = reason[:100]
            notice = "\nYour afk reason was shortened to 100 characters."
    else:
        reason = ""

    sql.set_afk(update.effective_user.id, reason)
    fname = update.effective_user.first_name
    try:
        await update.effective_message.reply_text("{} is now away!{}".format(fname, notice))
    except BadRequest:
        pass


async def no_longer_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user:
        return

    res = sql.rm_afk(user.id)
    if res:
        if message.new_chat_members:
            return
        firstname = update.effective_user.first_name
        try:
            options = [
                "{} is here!",
                "{} is back!",
                "{} is now in the chat!",
                "{} is awake!",
                "{} is back online!",
                "{} is finally here!",
                "Welcome back! {}",
                "Where is {}?\nIn the chat!",
            ]
            chosen_option = random.choice(options)
            await update.effective_message.reply_text(chosen_option.format(firstname))
        except:
            return


async def reply_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    message = update.effective_message
    userc = update.effective_user
    userc_id = userc.id

    entities = message.parse_entities([MessageEntityType.TEXT_MENTION, MessageEntityType.MENTION])

    if entities:
        chk_users = []
        for ent in entities:
            if ent.type == MessageEntityType.TEXT_MENTION:
                user_id = ent.user.id
                fst_name = ent.user.first_name

                if user_id in chk_users:
                    continue
                chk_users.append(user_id)

            elif ent.type == MessageEntityType.MENTION:
                user_id = await get_user_id(bot, message.text[ent.offset : ent.offset + ent.length])
                if not user_id:
                    continue

                if user_id in chk_users:
                    continue
                chk_users.append(user_id)

                try:
                    chat = await bot.get_chat(user_id)
                except BadRequest:
                    continue
                fst_name = chat.first_name
            else:
                continue

            await check_afk(update, context, user_id, fst_name, userc_id)

    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        fst_name = message.reply_to_message.from_user.first_name
        await check_afk(update, context, user_id, fst_name, userc_id)


async def check_afk(update, context, user_id, fst_name, userc_id):
    if sql.is_afk(user_id):
        user = sql.check_afk_status(user_id)
        if int(userc_id) == int(user_id):
            return
        if not user.reason:
            res = "{} is afk".format(fst_name)
            await update.effective_message.reply_text(res)
        else:
            res = "{} is afk.\nReason: <code>{}</code>".format(
                html.escape(fst_name), html.escape(user.reason)
            )
            await update.effective_message.reply_text(res, parse_mode=ParseMode.HTML)


__help__ = """
*Away from group*
 ❍ /afk <reason>*:* mark yourself as AFK(away from keyboard).
 ❍ brb <reason>*:* same as the afk command - but not a command.
When marked as AFK, any mentions will be replied to with a message to say you're not available!
"""

AFK_HANDLER = DisableAbleCommandHandler("afk", afk)
AFK_REGEX_HANDLER = DisableAbleMessageHandler(
  filters.Regex(r"(?i)^brb(.*)$"), afk, friendly="afk"
)
NO_AFK_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS, no_longer_afk
)
AFK_REPLY_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS, reply_afk
)

application.add_handler(AFK_HANDLER, AFK_GROUP)
application.add_handler(AFK_REGEX_HANDLER, AFK_GROUP)
application.add_handler(NO_AFK_HANDLER, AFK_GROUP)
application.add_handler(AFK_REPLY_HANDLER, AFK_REPLY_GROUP)

__mod_name__ = "Aꜰᴋ​"
__command_list__ = ["afk"]
__handlers__ = [
    (AFK_HANDLER, AFK_GROUP),
    (AFK_REGEX_HANDLER, AFK_GROUP),
    (NO_AFK_HANDLER, AFK_GROUP),
    (AFK_REPLY_HANDLER, AFK_REPLY_GROUP),
]
