import db, traceback, calendar, datetime, asyncio, sys, string, random, time, os, aiofiles, aiofiles.os
from typing import Union

from pyrogram import Client as BotClient, filters, raw, idle
from pyrogram.errors import ChatAdminRequired, FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from config import config
from fsubs_handler import handle_fsub
from functions import b64_to_string, string_to_b64


class Client(BotClient):
    def __init__(self, session_name, api_id, api_hash, bot_token):
        super().__init__(session_name, api_id, api_hash, bot_token=bot_token)
        self.fsub_ch_link = None
        self.bot_username = None

    async def add_user_(self, m: Message):
        user_id = m.from_user.id
        if not await db.is_exist(user_id):
            await db.add_user(user_id)
            if config.log_channel:
                await self.send_message(
                    config.log_channel,
                    f"#NEW_USER\n\nNama: {m.from_user.first_name}\nId: {m.from_user.id}\nLink: {m.from_user.mention}"
                )

    async def start(self):
        await super().start()
        try:
            invite_link = await self.export_chat_invite_link(config.log_channel)
            self.fsub_ch_link = invite_link
        except ChatAdminRequired:
            await self.send_message(
                config.log_channel,
                "**Bot harus menjadi admin di channel force subs!**\n**Sistem dimatikan**"
            )
            return sys.exit()
        self.bot_username = (await self.get_me()).username

    async def stop(self, *args, **kwargs):
        return await super().stop()

    async def leave_chat(
        self,
        chat_id: Union[int, str],
        delete: bool = False
    ):
        await self.send_message(
            chat_id,
            "**Maaf, chat ini ada pada list banned dan tidak bisa diakses!**",
        )
        peer = await self.resolve_peer(chat_id)

        if isinstance(peer, raw.types.InputPeerChannel):
            return await self.send(
                raw.functions.channels.LeaveChannel(
                    channel=await self.resolve_peer(chat_id)
                )
            )
        elif isinstance(peer, raw.types.InputPeerChat):
            r = await self.send(
                raw.functions.messages.DeleteChatUser(
                    chat_id=peer.chat_id,
                    user_id=raw.types.InputUserSelf()
                )
            )

            if delete:
                await self.send(
                    raw.functions.messages.DeleteHistory(
                        peer=peer,
                        max_id=0
                    )
                )

            return r


bot = Client(
    ":memory:",
    config.api_id,
    config.api_hash,
    bot_token=config.bot_token
)
media_list = {}


@bot.on_message(filters.command("start") & filters.private)
async def start_hndlr(c: Client, m: Message):
    status = await db.get_ban_status(m.from_user.id)
    if status:
        return await m.reply("Maaf, anda terban oleh owner kami.")
    if len(m.command) == 1:
        await c.add_user_(m)
        return await m.reply(
            "Hi",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("About Bot", "aboutbot"),
                        InlineKeyboardButton("About Dev", "aboutdev")
                    ]
                ]
            )
        )


@bot.on_message(filters.command('total') & filters.private)
async def sts(c, m):
    if m.from_user.id != config.owner_id:
        return
    await c.add_user_(m)
    total_users = await db.get_total_users()
    await m.reply_text(text=f"Total user(s) {total_users}", quote=True)


@bot.on_message(filters.command('ban') & filters.private)
async def _ban(c, m):
    if m.from_user.id != config.owner_id:
        return
    await c.add_user_(m)
    try:
         user = int(m.command[1])
    except ValueError:
         return
    await db.ban_user(user)
    await m.reply(f'Banned {user}', quote=True)

@bot.on_message(filters.command('unban') & filters.private)
async def _unban(c, m):
    if m.from_user.id != config.owner_id:
        return
    await c.add_user_(m)
    try:
        user_id = int(m.command[1])
    except ValueError:
        return
    await db.del_ban(user_id)
    await m.reply(f'Removed ban of {user_id}', quote=True)


CURRENT_PROCESSES = {}
CHAT_FLOOD = {}
broadcast_ids = {}

async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return 200, None
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        return 400, f"{user_id} : deactivated\n"
    except UserIsBlocked:
        return 400, f"{user_id} : blocked the bot\n"
    except PeerIdInvalid:
        return 400, f"{user_id} : user id invalid\n"
    except Exception as e:
        return 500, f"{user_id} : {traceback.format_exc()}\n"
        

@bot.on_message(filters.command('broadcast') & filters.reply & filters.private)
async def broadcast_(c, m):
    if m.from_user.id != config.owner_id:
        return
    await c.add_user_(m)
    all_users = await db.get_all_users()
    
    broadcast_msg = m.reply_to_message
    
    while True:
        broadcast_id = ''.join([random.choice(string.ascii_letters) for i in range(3)])
        if not broadcast_ids.get(broadcast_id):
            break
    
    out = await m.reply_text(
        text = f"Broadcast initiated! You will be notified with log file when all the users are notified."
    )
    start_time = time.time()
    total_users = await db.get_total_users()
    done = 0
    failed = 0
    success = 0
    
    broadcast_ids[broadcast_id] = dict(
        total = total_users,
        current = done,
        failed = failed,
        success = success
    )
    
    async with aiofiles.open('broadcast.txt', 'w') as broadcast_log_file:
        async for user in all_users:
            
            sts, msg = await send_msg(
                user_id = int(user['user_id']),
                message = broadcast_msg
            )
            if msg is not None:
                await broadcast_log_file.write(msg)
            
            if sts == 200:
                success += 1
            else:
                failed += 1
            
            if sts == 400:
                await db.del_user(user['user_id'])
            
            done += 1
            if broadcast_ids.get(broadcast_id) is None:
                break
            else:
                broadcast_ids[broadcast_id].update(
                    dict(
                        current = done,
                        failed = failed,
                        success = success
                    )
                )
    if broadcast_ids.get(broadcast_id):
        broadcast_ids.pop(broadcast_id)
    completed_in = datetime.timedelta(seconds=int(time.time()-start_time))
    
    await asyncio.sleep(3)
    
    await out.delete()
    
    if failed == 0:
        await m.reply_text(
            text=f"broadcast completed in `{completed_in}`\n\nTotal users {total_users}.\nTotal done {done}, {success} success and {failed} failed.",
            quote=True
        )
    else:
        await m.reply_document(
            document='broadcast.txt',
            caption=f"broadcast completed in `{completed_in}`\n\nTotal users {total_users}.\nTotal done {done}, {success} success and {failed} failed.",
            quote=True
        )
    
    await aiofiles.os.remove('broadcast.txt')

@bot.on_message(
    filters.text
    | filters.media
    & ~filters.sticker
    & ~filters.edited
)
async def send_media_(c: Client, m: Message):
    await c.add_user_(m)
    status = await db.get_ban_status(m.from_user.id)
    if status:
        return await m.reply("Maaf, anda terban oleh owner kami.")
    dbx = await db.get_user(m.from_user.id)
    if dbx['limit'] != '':
        date = datetime.datetime.utcnow()
        utc_time = calendar.timegm(date.utctimetuple())
        if utc_time < int(dbx['limit']):
            return await m.reply('Pengguna hanya dapat melakukan pengiriman selama sekali sehari.')
        else:
            await db.del_limit(m.from_user.id)
    kk = await c.get_messages(m.chat.id, m.message_id)
    if m.from_user.id != OWNER_ID:
        try:
            for urls in kk['entities']:
                if urls['type'] == 'url':
                    return await m.reply('Link tidak di izinkan pada caption.')
                elif urls['type'] == 'mention':
                    return await m.reply('Mention tidak di izinkan pada caption.')
        except:
            pass
    chat_type = m.chat.type
    ch1 = (await c.get_chat(config.channel1)).title
    ch2 = (await c.get_chat(config.channel2)).title
    ch3 = (await c.get_chat(config.channel3)).title
    if chat_type == "private":
        await c.add_user_(m)
        return await m.reply(
            f"**Mau kirim {'media' if not m.text else 'pesan'} kemana?**",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(ch1, "channel1"),
                    InlineKeyboardButton(ch2, "channel2"),
                    InlineKeyboardButton(ch3, "channel3"),
                ]
            ]),
            quote=True
        )


@bot.on_callback_query(filters.regex(r"channel(\d+)"))
async def get_mode(c: Client, cb: CallbackQuery):
    m = cb.message
    match = int(cb.matches[0].group(1))
    message_id = m.reply_to_message.message_id
    if match == 1:
        channel_tujuan = config.channel1
    elif match == 2:
        channel_tujuan = config.channel2
    else:
        channel_tujuan = config.channel3
    tjx = (await c.get_chat(config.channel1)).invite_link
    x = await handle_fsub(c, m, tjx, channel_tujuan)
    if not x:
        return
    x = await c.copy_message(
        channel_tujuan,
        m.chat.id,
        message_id,
        caption=m.caption + f'\n\nDikirimkan melalui bot @{self.bot_username}' or None
    )
    if isinstance(x, Message):
        message_id = x.message_id
        chat_id = x.chat.id
    else:
        message_id = None
        chat_id = None
    await m.delete()
    await m.reply(
        "**Pesan berhasil terkirim, silakan lihat dengan klik tombol dibawah ini!**",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Klik disini", url=f"https://t.me/c/{str(chat_id)[4:]}/{message_id}")
            ]
        ])
    )
    date = datetime.datetime.utcnow()
    utc_time = calendar.timegm(date.utctimetuple()) + 86400
    if m.from_user.id != OWNER_ID:
        await db.add_limit(m.from_user.id, utc_time)
    fwd = await c.forward_messages(
        config.log_channel,
        m.chat.id,
        message_id
    )
    m = m.reply_to_message
    fwdx = await fwd.reply(
        (
            "**User mengirim pesan**\n"
            f"Nama: {m.from_user.first_name}\n"
            f"Id: {m.from_user.id}\n"
            f"Username: {m.from_user.mention}"
        )
    )
    await x.copy(
        config.log_channel,
        caption=f'[Data Lengkap](https://t.me/c/{str(fwdx.chat.id)[4:]}/{fwdx.message_id})'
    )


async def main():
    try:
        print("Berjalan")
        await bot.start()
        await idle()
        await bot.stop()
    except KeyboardInterrupt:
        return sys.exit()


asyncio.get_event_loop().run_until_complete(main())
