import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from collections import defaultdict

API_TOKEN = "8490692991:AAEREn6006SgYrGVcNv-4FOWTVTNE_1C23Y"
TARGET_CHANNEL = "@CosplayVibes"

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

# временное хранилище медиа-групп
media_groups = defaultdict(list)
# хранилище подготовленных постов
user_posts = {}


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Привет! Отправь мне репост поста из @ruruposts (с фото и текстом). "
        "Я соберу фото в один пост, позволю отредактировать текст и опубликовать в @CosplayVibes."
    )


# перехват медиа-групп (альбомов)
@dp.message(F.media_group_id)
async def handle_album(message: types.Message):
    user_id = message.from_user.id
    media_groups[(user_id, message.media_group_id)].append(message)

    await asyncio.sleep(1.5)  # дождаться, пока Telegram отправит все фото альбома
    group = media_groups.pop((user_id, message.media_group_id), [])

    if not group:
        return

    first_msg = group[0]
    if not first_msg.forward_from_chat or first_msg.forward_from_chat.username != "ruruposts":
        await message.answer("Пожалуйста, пришли репост из канала @ruruposts.")
        return

    photos = [m.photo[-1].file_id for m in group]
    caption = first_msg.caption or ""

    user_posts[user_id] = {"photos": photos, "text": caption}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
        [InlineKeyboardButton(text="✅ Отправить пост", callback_data="send_post")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ])

    media = []
    for i, file_id in enumerate(photos):
        if i == 0:
            media.append(InputMediaPhoto(media=file_id, caption=caption or "(без текста)", parse_mode=ParseMode.MARKDOWN))
        else:
            media.append(InputMediaPhoto(media=file_id))

    # отправляем предпросмотр альбома
    sent = await bot.send_media_group(chat_id=message.chat.id, media=media)
    # добавляем кнопки под последним фото альбома
    await bot.send_message(chat_id=message.chat.id, text="Предпросмотр поста:", reply_markup=kb)


# одиночное фото
@dp.message(F.photo & ~F.media_group_id)
async def handle_single_photo(message: types.Message):
    if not message.forward_from_chat or message.forward_from_chat.username != "ruruposts":
        await message.answer("Пожалуйста, пришли репост из канала @ruruposts.")
        return

    photos = [message.photo[-1].file_id]
    caption = message.caption or ""

    user_posts[message.from_user.id] = {"photos": photos, "text": caption}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
        [InlineKeyboardButton(text="✅ Отправить пост", callback_data="send_post")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ])

    await message.answer_photo(
        photo=photos[0],
        caption=caption or "(без текста)",
        reply_markup=kb
    )


@dp.callback_query(F.data == "edit_text")
async def edit_text(callback: types.CallbackQuery):
    await callback.message.answer(
        "Отправь новый текст поста (Markdown и [гиперссылки](https://example.com) поддерживаются):"
    )
    await callback.answer()
    user_posts[callback.from_user.id]["editing"] = True


@dp.message(F.text)
async def save_new_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_posts and user_posts[user_id].get("editing"):
        user_posts[user_id]["text"] = message.text
        user_posts[user_id]["editing"] = False

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить пост", callback_data="send_post")],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
        ])

        post = user_posts[user_id]
        media = []
        for i, file_id in enumerate(post["photos"]):
            if i == 0:
                media.append(InputMediaPhoto(media=file_id, caption=post["text"], parse_mode=ParseMode.MARKDOWN))
            else:
                media.append(InputMediaPhoto(media=file_id))

        await bot.send_media_group(chat_id=message.chat.id, media=media)
        await message.answer("Предпросмотр поста:", reply_markup=kb)


@dp.callback_query(F.data == "send_post")
async def send_post(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    post = user_posts.get(user_id)
    if not post:
        await callback.answer("Нет данных для отправки.", show_alert=True)
        return

    media = []
    for i, file_id in enumerate(post["photos"]):
        if i == 0:
            media.append(InputMediaPhoto(media=file_id, caption=post["text"], parse_mode=ParseMode.MARKDOWN))
        else:
            media.append(InputMediaPhoto(media=file_id))

    await bot.send_media_group(chat_id=TARGET_CHANNEL, media=media)
    await callback.message.answer("✅ Пост успешно опубликован в канале!")
    await callback.answer()
    user_posts.pop(user_id, None)


@dp.callback_query(F.data == "cancel")
async def cancel(callback: types.CallbackQuery):
    user_posts.pop(callback.from_user.id, None)
    await callback.message.answer("❌ Публикация отменена.")
    await callback.answer()


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
