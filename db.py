# (c) @AbirHasan2005 | X-Noid

import motor.motor_asyncio
from config import config
col = motor.motor_asyncio.AsyncIOMotorClient(config.mongo_db)['channelxbot']['users']

def new_user(id):
    return dict(
        user_id=id,
        is_banned=False,
        limit=''
    )

async def add_user(id):
    user = new_user(id)
    await col.insert_one(user)

async def is_exist(id):
    user = await col.find_one({'user_id':int(id)})
    return True if user else False

async def get_total_users():
    count = await col.count_documents({})
    return count

async def get_all_users():
    all_users = col.find({})
    return all_users

async def del_user(user_id):
    await col.delete_many({'user_id': int(user_id)})

async def del_ban(user_id):
    await col.update_one({'user_id': user_id}, {'$set': {'is_banned': False}})

async def ban_user(user_id):
    await col.update_one({'user_id': user_id}, {'$set': {'is_banned': True}})

async def get_ban_status(id):
    user = await col.find_one({'user_id': id})
    if user is not None:
        return user['is_banned']
    else:
        return False

async def get_all_banned_user():
    banned_users = col.find({'is_banned': True})
    return banned_users

async def del_limit(user_id):
    await col.update_one({'user_id': user_id}, {'$set': {'limit': ''}})

async def add_limit(user_id, limit):
    await col.update_one({'user_id': user_id}, {'$set': {'limit': str(limit)}})

async def get_user(id):
    return await col.find_one({'id': id})