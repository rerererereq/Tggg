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
from aiohttp import web

logging.basicConfig(level=logging.INFO)
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


def get_channel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Перейти в канал", url=CHANNEL_LINK)]
    ])


def get_join_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Перейти в канал", callback_data="get_invite_link")]
    ])


def get_new_link_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Получить новую ссылку", callback_data="new_invite_link")]
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
        logger.error(f"Error checking channel membership: {e}")
        return False


async def create_invite_link() -> Optional[str]:
    try:
        expire_date = datetime.now() + timedelta(seconds=60)
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            expire_date=expire_date,
            member_limit=1
        )
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Error creating invite link: {e}")
        return None


async def expire_invite_message(chat_id: int, message_id: int):
    await asyncio.sleep(60)
    try:
        expired_text = "🚨 Срок действия ссылки истек. Запросите новую!"
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=expired_text,
            reply_markup=get_new_link_button()
        )
    except Exception as e:
        logger.error(f"Error updating expired message: {e}")


async def edit_to_invite_link(chat_id: int, message_id: int) -> None:
    invite_link = await create_invite_link()
    
    if invite_link:
        invite_text = f"🔐 Ваша инвайт-ссылка:\n{invite_link}\n\n❗️ Инвайт одноразовый и действителен 60 сек."
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=invite_text
        )
        asyncio.create_task(expire_invite_message(chat_id, message_id))
    else:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ Не удалось создать ссылку. Попробуйте позже.",
            reply_markup=get_new_link_button()
        )


@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    is_member = await check_user_in_channel(user_id)
    
    if is_member:
        member_text = (
            "🤖 Спасибо за сообщение, я бот и не могу на них отвечать.\n\n"
            "🪪 Я вижу, что ты уже участник нашего канала - <u>там есть вся информация</u>. "
            "<b>Остались вопросы?</b>\n\n"
            f"<b>Для консультации напишите нам:</b> {ADMIN_CONTACT} ✅"
        )
        await message.answer(member_text, reply_markup=get_channel_button(), parse_mode=ParseMode.HTML)
    else:
        welcome_text = (
            "<b>☑️ Приглашаем Вас в наш канал, где Вы ознакомитесь с гарантиями, "
            "отзывами и услугами, а так же найдете способы связи с нами для оформления 🪪\n\n"
            "Нажмите на кнопку ниже для того чтобы получить ссылку для вступления в канал👇👇👇</b>"
        )
        await message.answer(welcome_text, reply_markup=get_join_button(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "get_invite_link")
async def callback_get_invite_link(callback: CallbackQuery):
    await callback.answer()
    
    await edit_to_invite_link(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id
    )


@router.callback_query(F.data == "new_invite_link")
async def callback_new_invite_link(callback: CallbackQuery):
    await callback.answer()
    
    await edit_to_invite_link(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id
    )


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
        logger.info(f"HTTP server started on port {PORT}")
        return runner
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")
        raise


async def main():
    dp.include_router(router)
    logger.info("Bot is starting...")
    logger.info(f"BOT_TOKEN: {'*' * 10}")
    logger.info(f"CHANNEL_ID: {CHANNEL_ID}")
    logger.info(f"PORT: {PORT}")
    
    # Удаляем вебхук чтобы избежать конфликта с другими instance'ами
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted")
    except Exception as e:
        logger.warning(f"Could not delete webhook: {e}")
    
    http_runner = None
    try:
        http_runner = await run_http_server()
        logger.info("HTTP server ready, starting polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        if http_runner:
            await http_runner.cleanup()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
