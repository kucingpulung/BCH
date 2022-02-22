from pyrogram.errors import UserNotParticipant

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config


async def handle_fsub(c, m, tujuan, channel):
    try:
        user = await c.get_chat_member(channel, m.from_user.id)
        if user.status not in ["creator", "member", "administrator"] and user.status == "kicked":
            await c.send_message(
                m.from_user.id,
                "You are not allowed to use this bot.",
                reply_to_message_id=m.message_id
            )
            return False
        return True
    except UserNotParticipant:
        await c.send_message(
            m.from_user.id,
            "**Masuk ke channel terlebih dahulu untuk menggunakan bot!**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Channel", tujuan)
                    ]
                ]
            )
        )
        return False
