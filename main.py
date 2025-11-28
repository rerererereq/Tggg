#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.client.session import aiohttp_key
from aiohttp import web, TCPConnector
import aiohttp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/your_channel")
ADMIN_CONTACT = os.environ.get("ADMIN_CONTACT", "@VladimirMpeoRU")
PORT = int(os.environ.get("PORT", 10000))
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID environment variable is required!")
# Configure bot with connection pooling
session = aiohttp.ClientSession(
    connector=TCPConnector(limit=100, limit_per_host=30),
    timeout=aiohttp.ClientTimeout(total=30)
)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()
router = Router()
def get_channel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Перейти в канал", url=CHANNEL_LINK)]
    ])
def get_join_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Получить ссылку", callback_data="get_invite_link")]
    ])
def get_new_link_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Новая ссылка", callback_data="new_invite_link")]
    ])
async def check_user_in_channel(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception as e:
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        return False
async def create_invite_link() -> Optional[str]:
    try:
        expire_date = datetime.now() + timedelta(seconds=60)
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            expire_date=expire_date,
            member_limit=1
        )
        logger.info(f"Created invite link: {invite_link.invite_link[:30]}...")
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Error creating invite link: {e}")
        return None
async def expire_invite_message(chat_id: int, message_id: int):
    await asyncio.sleep(60)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🚨 Срок действия ссылки истек. Запросите новую!",
            reply_markup=get_new_link_button()
        )
        logger.info(f"Updated message {message_id} - link expired")
    except Exception as e:
        logger.error(f"Error updating expired message: {e}")
async def edit_to_invite_link(chat_id: int, message_id: int) -> None:
    try:
        invite_link = await create_invite_link()
        
        if invite_link:
            invite_text = f"🔐 Ваша инвайт-ссылка (60 сек):\n\n{invite_link}\n\n❗️ Одноразовый"
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=invite_text
            )
            asyncio.create_task(expire_invite_message(chat_id, message_id))
            logger.info(f"Sent invite link to {chat_id}")
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Ошибка создания ссылки. Попробуйте позже.",
                reply_markup=get_new_link_button()
            )
            logger.error(f"Failed to create invite link for {chat_id}")
    except Exception as e:
        logger.error(f"Error in edit_to_invite_link: {e}")
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    try:
        logger.info(f"START: Received /start from user {user_id}")
        
        is_member = await check_user_in_channel(user_id)
        logger.info(f"START: User {user_id} is_member={is_member}")
        
        if is_member:
            text = (
                "🤖 Спасибо за сообщение!\n\n"
                "🪪 Ты уже в нашем канале - там вся информация.\n\n"
                f"📞 Вопросы? Напиши: {ADMIN_CONTACT}"
            )
            await message.answer(text, reply_markup=get_channel_button())
            logger.info(f"START: Sent MEMBER response to {user_id}")
        else:
            text = (
                "☑️ Приглашаем в наш канал!\n\n"
                "Получи одноразовую ссылку на кнопке ниже 👇"
            )
            await message.answer(text, reply_markup=get_join_button())
            logger.info(f"START: Sent WELCOME response to {user_id}")
            
    except Exception as e:
        logger.error(f"START: ERROR for user {user_id}: {e}", exc_info=True)
        try:
            await message.answer("❌ Ошибка. Попробуйте позже.")
        except:
            pass
@router.callback_query(F.data == "get_invite_link")
async def callback_get_invite_link(callback: CallbackQuery):
    try:
        await callback.answer()
        logger.info(f"CALLBACK: get_invite_link from {callback.from_user.id}")
        await edit_to_invite_link(callback.message.chat.id, callback.message.message_id)
    except Exception as e:
        logger.error(f"CALLBACK: Error in get_invite_link: {e}")
@router.callback_query(F.data == "new_invite_link")
async def callback_new_invite_link(callback: CallbackQuery):
    try:
        await callback.answer()
        logger.info(f"CALLBACK: new_invite_link from {callback.from_user.id}")
        await edit_to_invite_link(callback.message.chat.id, callback.message.message_id)
    except Exception as e:
        logger.error(f"CALLBACK: Error in new_invite_link: {e}")
async def health_check(request):
    return web.Response(text="OK", status=200)
async def run_http_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"✓ HTTP server started on 0.0.0.0:{PORT}")
        return runner
    except Exception as e:
        logger.error(f"✗ Failed to start HTTP server: {e}")
        raise
async def main():
    dp.include_router(router)
    logger.info("=" * 60)
    logger.info("🚀 BOT STARTING")
    logger.info(f"   BOT_TOKEN: {'*' * 15}")
    logger.info(f"   CHANNEL_ID: {CHANNEL_ID}")
    logger.info(f"   PORT: {PORT}")
    logger.info("=" * 60)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✓ Webhook deleted")
    except Exception as e:
        logger.warning(f"⚠ Could not delete webhook: {e}")
    
    http_runner = None
    try:
        http_runner = await run_http_server()
        logger.info("✓ Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"✗ Bot error: {e}", exc_info=True)
    finally:
        if http_runner:
            await http_runner.cleanup()
        await session.close()
        logger.info("✓ Bot stopped")
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
