#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
# This file is part of < https://github.com/TheAloneTeam/MeowRobot > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/MeowRobot/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import importlib
import re
import time
import html
import traceback
import json
from platform import python_version as y
from sys import argv

from pyrogram import __version__ as pyrover
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode, ChatType
from telegram import __version__ as telever
from telegram.error import (
    BadRequest,
    ChatMigrated,
    NetworkError,
    TelegramError,
    TimedOut,
    Forbidden,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    MessageHandler,
    ContextTypes,
)
from telegram.helpers import escape_markdown
from telethon import __version__ as tlhver
import MeowRobot.modules.sql.users_sql as sql
from MeowRobot.modules.sql import SESSION, initialize_tables
from MeowRobot import (
    LOGGER,
    OWNER_ID,
    START_IMG,
    SUPPORT_CHAT,
    SUPPORT_CHANNEL,
    TOKEN,
    StartTime,
    application,
    pbot,
    telethn,
)
from MeowRobot.modules import ALL_MODULES
from MeowRobot.modules.helper_funcs.chat_status import is_user_admin
from MeowRobot.modules.helper_funcs.misc import paginate_modules

# Global variables to be set in main()
BOT_ID = 7163382841
BOT_NAME = "MeowRoBot"
BOT_USERNAME = "MeowRoBot"
START_IMG = "https://files.catbox.moe/v00l7e.jpg"
def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "

    time_list.reverse()
    ping_time += ":".join(time_list)

    return ping_time


PM_START_TEXT = """
ʜᴇʏ {} , 🥀
๏ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ *{}* ✨
➻ ᴀɴ ᴀʟʟ-ɪɴ-ᴏɴᴇ ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ ʙᴏᴛ  
ᴅᴇsɪɢɴᴇᴅ ᴛᴏ ᴍᴀᴋᴇ ʏᴏᴜʀ ᴄʜᴀᴛs sᴍᴀʀᴛ, sᴍᴏᴏᴛʜ & ғᴜɴ 💫
๏ ᴛᴀᴘ ᴏɴ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴍᴏᴅᴜʟᴇs & ᴄᴏᴍᴍᴀɴᴅs.
➥ ʟᴇᴛ’s ɢᴇᴛ sᴛᴀʀᴛᴇᴅ 💫
"""

def get_buttons():
    return [
        [
            InlineKeyboardButton(
                text="ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(text="❄ ᴀʙᴏᴜᴛ ❄", callback_data="MeowRoBot_"),
            InlineKeyboardButton(text="✨ sᴜᴩᴩᴏʀᴛ ✨", url=f"https://t.me/{SUPPORT_CHAT}"),
        ],
        [
            InlineKeyboardButton(text="📢 ᴜᴩᴅᴀᴛᴇs 📢", url=f"https://t.me/{SUPPORT_CHANNEL}"),
            InlineKeyboardButton(text="☁️ sᴏᴜʀᴄᴇ ☁️", callback_data="source_"),
        ],
        [
            InlineKeyboardButton(text="🥀 ᴅᴇᴠᴇʟᴏᴩᴇʀ 🥀", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton(text="ʜᴇʟᴩ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_back"),
        ],
    ]

HELP_STRINGS = ""

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []
CHAT_SETTINGS = {}
USER_SETTINGS = {}

async def send_help(chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    if len(text) > 1024:
        await application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
    else:
        await application.bot.send_photo(
            chat_id=chat_id,
            photo=START_IMG,
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


async def edit_message(query, text, keyboard, parse_mode=ParseMode.MARKDOWN):
    try:
        if len(text) > 1024:
            if query.message.caption:
                await query.message.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                await query.message.delete()
            else:
                await query.edit_message_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
        else:
            if not query.message.caption:
                await query.message.reply_photo(
                    photo=START_IMG,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                )
                await query.message.delete()
            else:
                await query.edit_message_caption(
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                )
    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        else:
            raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    uptime = get_readable_time((time.time() - StartTime))

    if update.effective_chat.type == ChatType.PRIVATE or update.effective_chat.type == "private":
        if len(args) >= 1:
            if args[0].lower() == "help":
                await send_help(update.effective_chat.id, HELP_STRINGS)

            elif args[0].lower().startswith("ghelp_"):
                mod = args[0].lower().split("_", 1)[1]
                if not HELPABLE.get(mod, False):
                    return
                await send_help(
                    update.effective_chat.id,
                    HELPABLE[mod].__help__,
                    InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="◁", callback_data="help_back")]]
                    ),
                )

            elif args[0].lower() == "markdownhelp":
                await IMPORTED["exᴛʀᴀs"].markdown_help_sender(update, context)

            elif args[0].lower().startswith("stngs_"):
                match = re.match("stngs_(.*)", args[0].lower())
                chat = await context.bot.get_chat(match.group(1))

                if await is_user_admin(chat, update.effective_user.id):
                    await send_settings(match.group(1), update.effective_user.id, False)
                else:
                    await send_settings(match.group(1), update.effective_user.id, True)

            elif args[0][1:].isdigit() and "rᴜʟᴇs" in IMPORTED:
                await IMPORTED["rᴜʟᴇs"].send_rules(update, args[0], from_pm=True)

        else:
            first_name = update.effective_user.first_name
            text = PM_START_TEXT.format(escape_markdown(first_name), escape_markdown(BOT_NAME))
            if len(text) > 1024:
                await update.effective_message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(get_buttons()),
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.effective_message.reply_photo(
                    photo=START_IMG,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(get_buttons()),
                    parse_mode=ParseMode.MARKDOWN,
                )

    else:
        await update.effective_message.reply_photo(
            START_IMG,
            caption="ɪ ᴀᴍ ᴀʟɪᴠᴇ ʙᴀʙʏ !\n*ɪ ᴅɪᴅɴ'ᴛ sʟᴇᴘᴛ sɪɴᴄᴇ:* `{}`".format(
                uptime
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

async def error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    LOGGER.error(msg="Exception while handling an update:", exc_info=error)

    try:
        raise error
    except Forbidden:
        pass
    except BadRequest:
        pass
    except TimedOut:
        pass
    except NetworkError:
        pass
    except ChatMigrated as err:
        pass
    except TelegramError:
        pass


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)

    try:
        if mod_match:
            module = mod_match.group(1)
            text = (
                "» *ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs ꜰᴏʀ* *{}* :\n".format(
                    HELPABLE[module].__mod_name__
                )
                + HELPABLE[module].__help__
            )
            await edit_message(
                query,
                text,
                InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="◁", callback_data="help_back")]]
                ),
            )

        elif prev_match:
            curr_page = int(prev_match.group(1))
            await edit_message(
                query,
                HELP_STRINGS,
                InlineKeyboardMarkup(paginate_modules(curr_page - 1, HELPABLE, "help")),
            )

        elif next_match:
            next_page = int(next_match.group(1))
            await edit_message(
                query,
                HELP_STRINGS,
                InlineKeyboardMarkup(paginate_modules(next_page + 1, HELPABLE, "help")),
            )

        elif back_match:
            await edit_message(
                query,
                HELP_STRINGS,
                InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help")),
            )

        await context.bot.answer_callback_query(query.id)

    except BadRequest:
        pass


async def MeowRoBot_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "MeowRoBot_":
        uptime = get_readable_time((time.time() - StartTime))
        text = (
            f"*ʜᴇʏ,*🥀\n  *ᴛʜɪs ɪs {BOT_NAME}*"
            "\n*ᴀ ᴘᴏᴡᴇʀꜰᴜʟ ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ ʙᴏᴛ ʙᴜɪʟᴛ ᴛᴏ ʜᴇʟᴘ ʏᴏᴜ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴇᴀꜱɪʟʏ ᴀɴᴅ ᴛᴏ ᴘʀᴏᴛᴇᴄᴛ ʏᴏᴜʀ ɢʀᴏᴜᴘ ꜰʀᴏᴍ ꜱᴄᴀᴍᴍᴇʀꜱ ᴀɴᴅ ꜱᴘᴀᴍᴍᴇʀꜱ.*"
            "\n*ᴡʀɪᴛᴛᴇɴ ɪɴ ᴩʏᴛʜᴏɴ ᴡɪᴛʜ sǫʟᴀʟᴄʜᴇᴍʏ ᴀɴᴅ ᴍᴏɴɢᴏᴅʙ ᴀs ᴅᴀᴛᴀʙᴀsᴇ.*"
            "\n\n────────────────────"
            f"\n*➻ ᴜᴩᴛɪᴍᴇ »* {uptime}"
            f"\n*➻ ᴜsᴇʀs »* {sql.num_users()}"
            f"\n*➻ ᴄʜᴀᴛs »* {sql.num_chats()}"
            "\n────────────────────"
            "\n\n➲  ɪ ᴄᴀɴ ʀᴇꜱᴛʀɪᴄᴛ ᴜꜱᴇʀꜱ."
            "\n➲  ɪ ʜᴀᴠᴇ ᴀɴ ᴀᴅᴠᴀɴᴄᴇᴅ ᴀɴᴛɪ-ꜰʟᴏᴏᴅ ꜱʏꜱᴛᴇᴍ."
            "\n➲  ɪ ᴄᴀɴ ɢʀᴇᴇᴛ ᴜꜱᴇʀꜱ ᴡɪᴛʜ ᴄᴜꜱᴛᴏᴍɪᴢᴀʙʟᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ ᴀɴᴅ ᴇᴠᴇɴ ꜱᴇᴛ ᴀ ɢʀᴏᴜᴘ's ʀᴜʟᴇꜱ."
            "\n➲  ɪ ᴄᴀɴ ᴡᴀʀɴ ᴜꜱᴇʀꜱ ᴜɴᴛɪʟ ᴛʜᴇʏ ʀᴇᴀᴄʜ ᴍᴀx ᴡᴀʀɴꜱ, ᴡɪᴛʜ ᴇᴀᴄʜ ᴘʀᴇᴅᴇꜰɪɴᴇᴅ ᴀᴄᴛɪᴏɴꜱ ꜱᴜᴄʜ ᴀꜱ ʙᴀɴ, ᴍᴜᴛᴇ, ᴋɪᴄᴋ, ᴇᴛᴄ."
            "\n➲  ɪ ʜᴀᴠᴇ ᴀ ɴᴏᴛᴇ ᴋᴇᴇᴘɪɴɢ ꜱʏꜱᴛᴇᴍ, ʙʟᴀᴄᴋʟɪꜱᴛꜱ, ᴀɴᴅ ᴇᴠᴇɴ ᴘʀᴇᴅᴇᴛᴇʀᴍɪɴᴇᴅ ʀᴇᴘʟɪᴇꜱ ᴏɴ ᴄᴇʀᴛᴀɪɴ ᴋᴇʏᴡᴏʀᴅꜱ."
            f"\n\n➻ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ɢɪᴠᴇɴ ʙᴇʟᴏᴡ ғᴏʀ ɢᴇᴛᴛɪɴɢ ʙᴀsɪᴄ ʜᴇʟᴩ ᴀɴᴅ ɪɴғᴏ ᴀʙᴏᴜᴛ {BOT_NAME}."
        )
        await edit_message(
            query,
            text,
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="sᴜᴩᴩᴏʀᴛ", callback_data="MeowRoBot_support"
                        ),
                        InlineKeyboardButton(
                            text="ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_back"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="ᴅᴇᴠᴇʟᴏᴩᴇʀ", url=f"tg://user?id={OWNER_ID}"
                        ),
                        InlineKeyboardButton(
                            text="sᴏᴜʀᴄᴇ",
                            callback_data="source_",
                        ),
                    ],
                    [
                        InlineKeyboardButton(text="◁", callback_data="MeowRoBot_back"),
                    ],
                ]
            ),
        )
    elif query.data == "MeowRoBot_support":
        text = (
            "*๏ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ɢɪᴠᴇɴ ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ ʜᴇʟᴩ ᴀɴᴅ ᴍᴏʀᴇ ɪɴғᴏʀᴍᴀᴛɪᴏɴ ᴀʙᴏᴜᴛ ᴍᴇ.*"
            f"\n\nɪғ ʏᴏᴜ ғᴏᴜɴᴅ ᴀɴʏ ʙᴜɢ ɪɴ {BOT_NAME} ᴏʀ ɪғ ʏᴏᴜ ᴡᴀɴɴᴀ ɢɪᴠᴇ ғᴇᴇᴅʙᴀᴄᴋ ᴀʙᴏᴜᴛ ᴛʜᴇ {BOT_NAME}, ᴩʟᴇᴀsᴇ ʀᴇᴩᴏʀᴛ ɪᴛ ᴀᴛ sᴜᴩᴩᴏʀᴛ ᴄʜᴀᴛ."
        )
        await edit_message(
            query,
            text,
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="sᴜᴩᴩᴏʀᴛ", url=f"https://t.me/{SUPPORT_CHAT}"
                        ),
                        InlineKeyboardButton(
                            text="ᴜᴩᴅᴀᴛᴇs", url=f"https://t.me/{SUPPORT_CHANNEL}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="ᴅᴇᴠᴇʟᴏᴩᴇʀ", url=f"tg://user?id={OWNER_ID}"
                        ),
                        InlineKeyboardButton(
                            text="ɢɪᴛʜᴜʙ",
                            url="https://github.com/TheAloneTeam/MeowRoBot",
                        ),
                    ],
                    [
                        InlineKeyboardButton(text="◁", callback_data="MeowRoBot_"),
                    ],
                ]
            ),
        )
    elif query.data == "MeowRoBot_back":
        first_name = update.effective_user.first_name
        await edit_message(
            query,
            PM_START_TEXT.format(escape_markdown(first_name), escape_markdown(BOT_NAME)),
            InlineKeyboardMarkup(get_buttons()),
            parse_mode=ParseMode.MARKDOWN,
        )


async def Source_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "source_":
        text = f"""
*ʜᴇʏ,
 ᴛʜɪs ɪs {BOT_NAME},
ᴀɴ ᴏᴩᴇɴ sᴏᴜʀᴄᴇ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴩ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ ʙᴏᴛ.*

ᴡʀɪᴛᴛᴇɴ ɪɴ ᴩʏᴛʜᴏɴ ᴡɪᴛʜ ᴛʜᴇ ʜᴇʟᴩ ᴏғ : [ᴛᴇʟᴇᴛʜᴏɴ](https://github.com/LonamiWebs/Telethon)
[ᴩʏʀᴏɢʀᴀᴍ](https://github.com/pyrogram/pyrogram)
[ᴩʏᴛʜᴏɴ-ᴛᴇʟᴇɢʀᴀᴍ-ʙᴏᴛ](https://github.com/python-telegram-bot/python-telegram-bot)
ᴀɴᴅ ᴜsɪɴɢ [sǫʟᴀʟᴄʜᴇᴍʏ](https://www.sqlalchemy.org) ᴀɴᴅ [ᴍᴏɴɢᴏ](https://cloud.mongodb.com) ᴀs ᴅᴀᴛᴀʙᴀsᴇ.


*ʜᴇʀᴇ ɪs ᴍʏ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ :* [ɢɪᴛʜᴜʙ](https://github.com/TheAloneTeam/MeowRoBot)


{BOT_NAME} ɪs ʟɪᴄᴇɴsᴇᴅ ᴜɴᴅᴇʀ ᴛʜᴇ [ᴍɪᴛ ʟɪᴄᴇɴsᴇ](https://github.com/TheAloneTeam/MeowRoBot/blob/master/LICENSE).
© 2022 - 2023 | [sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ](https://t.me/{SUPPORT_CHAT}), ᴀʟʟ ʀɪɢʜᴛs ʀᴇsᴇʀᴠᴇᴅ.
"""
        await edit_message(
            query,
            text,
            InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="◁", callback_data="source_back")]]
            ),
        )
    elif query.data == "source_back":
        first_name = update.effective_user.first_name
        await edit_message(
            query,
            PM_START_TEXT.format(escape_markdown(first_name), escape_markdown(BOT_NAME)),
            InlineKeyboardMarkup(get_buttons()),
            parse_mode=ParseMode.MARKDOWN,
        )


async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)

    # ONLY send help in PM
    if chat.type != chat.PRIVATE:
        if len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
            module = args[1].lower()
            text = f"Contact me in PM to get help of {module.capitalize()}"
            if len(text) > 1024:
                await update.effective_message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="ʜᴇʟᴘ",
                                    url="https://t.me/{}?start=ghelp_{}".format(
                                        context.bot.username, module
                                    ),
                                )
                            ]
                        ]
                    ),
                )
            else:
                await update.effective_message.reply_photo(
                    photo=START_IMG,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="ʜᴇʟᴘ",
                                    url="https://t.me/{}?start=ghelp_{}".format(
                                        context.bot.username, module
                                    ),
                                )
                            ]
                        ]
                    ),
                )
            return
        text = "» ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴩᴛɪᴏɴ ғᴏʀ ɢᴇᴛᴛɪɴɢ ʜᴇʟᴩ."
        if len(text) > 1024:
            await update.effective_message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="ᴏᴩᴇɴ ɪɴ ᴩʀɪᴠᴀᴛᴇ",
                                url="https://t.me/{}?start=help".format(
                                    context.bot.username
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="ᴏᴩᴇɴ ʜᴇʀᴇ",
                                callback_data="help_back",
                            )
                        ],
                    ]
                ),
            )
        else:
            await update.effective_message.reply_photo(
                photo=START_IMG,
                caption=text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="ᴏᴩᴇɴ ɪɴ ᴩʀɪᴠᴀᴛᴇ",
                                url="https://t.me/{}?start=help".format(
                                    context.bot.username
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="ᴏᴩᴇɴ ʜᴇʀᴇ",
                                callback_data="help_back",
                            )
                        ],
                    ]
                ),
            )
        return

    elif len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
        module = args[1].lower()
        text = (
            "Here is the available help for the *{}* module:\n".format(
                HELPABLE[module].__mod_name__
            )
            + HELPABLE[module].__help__
        )
        await send_help(
            chat.id,
            text,
            InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="◁", callback_data="help_back")]]
            ),
        )

    else:
        await send_help(chat.id, HELP_STRINGS)


async def send_settings(chat_id, user_id, user=False):
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                "*{}*:\n{}".format(mod.__mod_name__, mod.__user_settings__(user_id))
                for mod in USER_SETTINGS.values()
            )
            text = "These are your current settings:" + "\n\n" + settings
            if len(text) > 1024:
                await application.bot.send_message(
                    user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await application.bot.send_photo(
                    chat_id=user_id,
                    photo=START_IMG,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                )

        else:
            await application.bot.send_photo(
                chat_id=user_id,
                photo=START_IMG,
                caption="Seems like there aren't any user specific settings available :'(",
                parse_mode=ParseMode.MARKDOWN,
            )

    else:
        if CHAT_SETTINGS:
            chat_name = (await application.bot.get_chat(chat_id)).title
            text = "Which module would you like to check {}'s settings for?".format(
                chat_name
            )
            if len(text) > 1024:
                await application.bot.send_message(
                    user_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(
                        paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
                    ),
                )
            else:
                await application.bot.send_photo(
                    chat_id=user_id,
                    photo=START_IMG,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(
                        paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
                    ),
                )
        else:
            await application.bot.send_photo(
                chat_id=user_id,
                photo=START_IMG,
                caption="Seems like there aren't any chat settings available :'(\nSend this "
                "in a group chat you're admin in to find its current settings!",
                parse_mode=ParseMode.MARKDOWN,
            )


async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    bot = context.bot
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)
    try:
        if mod_match:
            chat_id = mod_match.group(1)
            module = mod_match.group(2)
            chat = await bot.get_chat(chat_id)
            text = "*{}* has the following settings for the *{}* module:\n\n".format(
                escape_markdown(chat.title), CHAT_SETTINGS[module].__mod_name__
            ) + CHAT_SETTINGS[module].__chat_settings__(chat_id, user.id)
            await edit_message(
                query,
                text,
                InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="◁", callback_data="stngs_back({})".format(chat_id))]]
                ),
            )

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = await bot.get_chat(chat_id)
            text = "Hi there! There are quite a few settings for {} - go ahead and pick what you're interested in.".format(chat.title)
            await edit_message(
                query,
                text,
                InlineKeyboardMarkup(paginate_modules(curr_page - 1, CHAT_SETTINGS, "stngs", chat=chat_id)),
            )

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = await bot.get_chat(chat_id)
            text = "Hi there! There are quite a few settings for {} - go ahead and pick what you're interested in.".format(chat.title)
            await edit_message(
                query,
                text,
                InlineKeyboardMarkup(paginate_modules(next_page + 1, CHAT_SETTINGS, "stngs", chat=chat_id)),
            )

        elif back_match:
            chat_id = back_match.group(1)
            chat = await bot.get_chat(chat_id)
            text = "Hi there! There are quite a few settings for {} - go ahead and pick what you're interested in.".format(escape_markdown(chat.title))
            await edit_message(
                query,
                text,
                InlineKeyboardMarkup(paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)),
            )

        await bot.answer_callback_query(query.id)
    except BadRequest as excp:
        if excp.message not in [
            "Message is not modified",
            "Query_id_invalid",
            "Message can't be deleted",
        ]:
            LOGGER.exception("Exception in settings buttons. %s", str(query.data))


async def get_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    # ONLY send settings in PM
    if chat.type != chat.PRIVATE:
        if await is_user_admin(chat, user.id):
            text = "Click here to get this chat's settings, as well as yours."
            await msg.reply_photo(
                photo=START_IMG,
                caption=text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="sᴇᴛᴛɪɴɢs",
                                url="t.me/{}?start=stngs_{}".format(
                                    context.bot.username, chat.id
                                ),
                            )
                        ]
                    ]
                ),
            )
        else:
            text = "Click here to check your settings."
            await msg.reply_photo(
                photo=START_IMG,
                caption=text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="sᴇᴛᴛɪɴɢs",
                                url="t.me/{}?start=stngs_{}".format(
                                    context.bot.username, chat.id
                                ),
                            )
                        ]
                    ]
                ),
            )

    else:
        await send_settings(chat.id, user.id, True)


async def migrate_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return

    LOGGER.info("Migrating from %s, to %s", str(old_chat), str(new_chat))

    for mod in MIGRATEABLE:
        if hasattr(mod, "__migrate__"):
            try:
                func = mod.__migrate__
                res = func(old_chat, new_chat)

                # ✅ only await if coroutine
                if hasattr(res, "__await__"):
                    await res

            except Exception as e:
                LOGGER.error(f"Migration error in {mod.__name__}: {e}")

    LOGGER.info("Successfully migrated!")

async def post_init(application: Application):
    global BOT_NAME, BOT_USERNAME, HELP_STRINGS

    # Get Bot info
    bot_info = await application.bot.get_me()
    BOT_NAME = bot_info.first_name
    BOT_USERNAME = bot_info.username

    HELP_STRINGS = f"""
*» {BOT_NAME} ᴇxᴄʟᴜsɪᴠᴇ ꜰᴇᴀᴛᴜʀᴇs*
➲ /start : ꜱᴛᴀʀᴛꜱ ᴍᴇ
➲ /help  : ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ
"""

    # ✅ INSIDE FUNCTION
    if SUPPORT_CHAT is not None and isinstance(SUPPORT_CHAT, str):
        try:
            await application.bot.send_message(
                chat_id=f"@{SUPPORT_CHAT}",
                text=f"🥀 {BOT_NAME} ɪs ᴀʟɪᴠᴇ ʙᴀʙʏ...",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Forbidden:
            LOGGER.warning(
                f"Bot isn't able to send message to @{SUPPORT_CHAT}, go and check!"
            )
        except BadRequest as e:
            LOGGER.warning(e.message)

    # Start clients
    await telethn.start(bot_token=TOKEN)
    await pbot.start()

    # Scheduler
    if "nɪɢʜᴛ" in IMPORTED:
        await IMPORTED["nɪɢʜᴛ"].start_scheduler()
        
if __name__ == "__main__":
    from MeowRobot.health_server import start_health_server
    start_health_server()

    # Import modules
    for module_name in ALL_MODULES:
        imported_module = importlib.import_module("MeowRobot.modules." + module_name)
        if not hasattr(imported_module, "__mod_name__"):
            imported_module.__mod_name__ = imported_module.__name__

        if imported_module.__mod_name__.lower() not in IMPORTED:
            IMPORTED[imported_module.__mod_name__.lower()] = imported_module
        else:
            raise Exception("Can't have two modules with the same name! Please change one")

        if hasattr(imported_module, "__help__") and imported_module.__help__:
            HELPABLE[imported_module.__mod_name__.lower()] = imported_module

        if hasattr(imported_module, "__migrate__"):
            MIGRATEABLE.append(imported_module)

        if hasattr(imported_module, "__stats__"):
            STATS.append(imported_module)

        if hasattr(imported_module, "__user_info__"):
            USER_INFO.append(imported_module)

        if hasattr(imported_module, "__import_data__"):
            DATA_IMPORT.append(imported_module)

        if hasattr(imported_module, "__export_data__"):
            DATA_EXPORT.append(imported_module)

        if hasattr(imported_module, "__chat_settings__"):
            CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

        if hasattr(imported_module, "__user_settings__"):
            USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

    initialize_tables()

    LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", get_help))
    application.add_handler(CallbackQueryHandler(help_button, pattern=r"help_.*"))
    application.add_handler(CommandHandler("settings", get_settings))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"stngs_"))
    application.add_handler(CallbackQueryHandler(MeowRoBot_about_callback, pattern=r"MeowRoBot_"))
    application.add_handler(CallbackQueryHandler(Source_about_callback, pattern=r"source_"))

    async def close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.message.delete()

    application.add_handler(CallbackQueryHandler(close_callback, pattern=r"close"))
    application.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, migrate_chats))


    application.add_error_handler(error_callback)

    application.post_init = post_init
    
    LOGGER.info("Starting MeowRoBot...")
    application.run_polling(
        timeout=15,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
