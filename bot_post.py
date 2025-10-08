import asyncio
import logging
from datetime import datetime
from collections import defaultdict
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

API_TOKEN = "8490692991:AAEREn6006SgYrGVcNv-4FOWTVTNE_1C23Y"
CHANNEL_ID = "@CosplayVibes"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_posts = defaultdict(dict)
media_groups = {}  # временное хранилище для альбомов


def preview_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
        [InlineKeyboardButton(text="✅ Отправить пост", callback_data="send_post")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_post")]
    ])


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        "Пришли репост из канала <b>https://t.me/ruruposts</b> — бот соберёт пост и покажет предпросмотр."
    )


@dp.message(F.forward_from_chat)
async def handle_forwarded(message: types.Message):
    """Обрабатывает пересланные посты из канала"""
    user_id = message.from_user.id

    # Альбом (медиагруппа)
    if message.media_group_id:
        mgid = message.media_group_id
        group = media_groups.setdefault(mgid, {
            "photos": [],
            "text": message.caption or "",
            "user_id": user_id,
            "last_update": datetime.now(),
        })

        if message.photo:
            group["photos"].append(message.photo[-1].file_id)
        group["last_update"] = datetime.now()
    else:
        # Одиночное фото
        photos = [message.photo[-1].file_id] if message.photo else []
        text = message.caption or "(без текста)"
        user_posts[user_id] = {"photos": photos, "text": text}
        await show_preview(user_id)


async def show_preview(user_id: int):
    """Показывает предпросмотр пользователю"""
    post = user_posts.get(user_id)
    if not post:
        return

    photos = post["photos"]
    text = post["text"]

    try:
        if len(photos) > 1:
            media = [
                InputMediaPhoto(media=photos[0], caption=text, parse_mode=ParseMode.HTML)
            ] + [InputMediaPhoto(media=p) for p in photos[1:]]
            await bot.send_media_group(chat_id=user_id, media=media)
            await bot.send_message(chat_id=user_id, text="📋 Предпросмотр поста:", reply_markup=preview_keyboard())
        elif len(photos) == 1:
            await bot.send_photo(chat_id=user_id, photo=photos[0], caption=text, reply_markup=preview_keyboard())
        else:
            await bot.send_message(chat_id=user_id, text=text, reply_markup=preview_keyboard())
    except Exception as e:
        await bot.send_message(chat_id=user_id, text=f"⚠️ Ошибка предпросмотра: {e}")


@dp.callback_query(F.data == "edit_text")
async def edit_text(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_posts:
        await callback.message.answer("⚠️ Нет поста для редактирования.")
        return
    user_posts[uid]["editing"] = True
    await callback.message.answer("✍️ Введите новый текст поста (HTML разрешён):")
    await callback.answer()


@dp.message()
async def handle_edit(message: types.Message):
    uid = message.from_user.id
    if uid in user_posts and user_posts[uid].get("editing"):
        user_posts[uid]["text"] = message.text
        user_posts[uid]["editing"] = False
        await message.answer("✅ Текст обновлён.")
        await show_preview(uid)


@dp.callback_query(F.data == "send_post")
async def send_post(callback: types.CallbackQuery):
    uid = callback.from_user.id
    post = user_posts.get(uid)
    if not post:
        await callback.message.answer("⚠️ Нет поста для отправки.")
        return

    photos, text = post["photos"], post["text"]

    try:
        if len(photos) > 1:
            media = [
                InputMediaPhoto(media=photos[0], caption=text, parse_mode=ParseMode.HTML)
            ] + [InputMediaPhoto(media=p) for p in photos[1:]]
            await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        elif len(photos) == 1:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=photos[0], caption=text, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)

        await callback.message.answer("✅ Пост опубликован в канал.")
        del user_posts[uid]
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка публикации: {e}")
    await callback.answer()


@dp.callback_query(F.data == "cancel_post")
async def cancel_post(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user_posts.pop(uid, None)
    await callback.message.answer("❌ Пост отменён.")
    await callback.answer()


async def check_albums():
    """Следит за завершением получения всех фото в альбоме"""
    while True:
        now = datetime.now()
        ready = []

        for mgid, data in list(media_groups.items()):
            if (now - data["last_update"]).total_seconds() > 2:
                ready.append(mgid)

        for mgid in ready:
            data = media_groups.pop(mgid)
            uid = data["user_id"]
            user_posts[uid] = {"photos": data["photos"], "text": data["text"]}
            await show_preview(uid)

        await asyncio.sleep(2)


async def main():
    print("Бот запущен...")
    asyncio.create_task(check_albums())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
