import logging
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Папка для сохранения фото
PHOTOS_DIR = "PHOTOS_DIR"
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# ID канала, куда будут репоститься посты (замените на ваш)
CHANNEL_ID = "@ruruposts"  # Например, "@my_test_channel"

# Глобальные переменные для хранения данных поста
user_data = {}

# Меню
menu_keyboard = ReplyKeyboardMarkup(
    [["Создать предложку"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Нажми 'Создать предложку', чтобы начать.",
        reply_markup=menu_keyboard
    )

# Обработка текста
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Если пользователь нажал "Создать предложку"
    if text == "Создать предложку":
        user_data[user_id] = {"photos": [], "message_ids": []}  # Инициализируем список фото и ID сообщений
        await update.message.reply_text(
            "Привет!\nОтправь данные по этой форме:\nFandom: (Фендом косплея)\nCharacter: (Персонаж Косплея)\nCosplayer: (Ваш ник)\nLinks: (Ссылки на вас (именно ссылка, пример: https://t.me/kimito_64))",
            reply_markup=None  # Убираем меню
        )
        return

    # Если пользователь редактирует текст
    if "edit_text" in user_data.get(user_id, {}):
        user_data[user_id]["text"] = text
        del user_data[user_id]["edit_text"]  # Убираем флаг редактирования
        await update.message.reply_text("Текст обновлен. Нажмите кнопку 'отправить' выше.")
        await show_preview(update, context, user_id)  # Показываем предпросмотр
        return

    # Сохраняем текст в глобальную переменную
    user_data[user_id]["text"] = text

    await update.message.reply_text("Теперь отправь фото для поста.")

# Обработка фото (сжатые изображения)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Проверяем, есть ли текст для этого пользователя
    if user_id not in user_data or "text" not in user_data[user_id]:
        await update.message.reply_text("Сначала отправь текст предложки.")
        return

    # Сохраняем фото
    photo_file = await update.message.photo[-1].get_file()
    file_path = os.path.join(PHOTOS_DIR, f"{user_id}_{len(user_data[user_id]['photos'])}.jpg")
    await photo_file.download_to_drive(file_path)

    # Добавляем путь к фото в список
    user_data[user_id]["photos"].append(file_path)

    # Удаляем предыдущие сообщения бота
    await delete_previous_messages(context, user_id)

    # Показываем предпросмотр
    await show_preview(update, context, user_id)

# Удаление предыдущих сообщений бота
async def delete_previous_messages(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if "message_ids" in user_data[user_id]:
        for message_id in user_data[user_id]["message_ids"]:
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=message_id
                )
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения: {e}")
        user_data[user_id]["message_ids"] = []  # Очищаем список ID сообщений

# Показ предпросмотра предложки
async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    # Отправляем текст и фото как единое сообщение
    text = user_data[user_id]["text"]
    photo_paths = user_data[user_id]["photos"]

    # Создаем медиагруппу
    media_group = []
    for i, photo_path in enumerate(photo_paths):
        with open(photo_path, "rb") as photo:
            if i == 0:
                # Первое фото с текстом
                media_group.append(InputMediaPhoto(media=photo, caption=text))
            else:
                # Остальные фото без текста
                media_group.append(InputMediaPhoto(media=photo))

    # Отправляем медиагруппу
    messages = await context.bot.send_media_group(
        chat_id=user_id,
        media=media_group
    )

    # Сохраняем ID сообщений для последующего удаления
    for message in messages:
        user_data[user_id]["message_ids"].append(message.message_id)

    # Создаем интерактивные кнопки
    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="publish")],
        [InlineKeyboardButton("✏️ Редактировать текст", callback_data="edit_text")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем кнопки
    message = await context.bot.send_message(
        chat_id=user_id,
        text="Если всё верно, нажмите '✅ Отправить'. Или выберите другое действие:",
        reply_markup=reply_markup
    )
    # Сохраняем ID последнего сообщения с кнопками
    user_data[user_id]["message_ids"].append(message.message_id)

# Обработка документов (файлов)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Отклоняем файлы и выводим сообщение об ошибке
    await update.message.reply_text("Нужно отправить только сжатые фото. Пожалуйста, отправь фото как изображение(сжатое), а не как файл.")

# Обработка нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # Обрабатываем нажатие кнопки
    if query.data == "publish":
        # Проверяем, есть ли текст и фото
        if user_id not in user_data or "text" not in user_data[user_id] or not user_data[user_id]["photos"]:
            await query.answer("Ошибка: данные не найдены.")
            return

        # Получаем текст и фото
        text = user_data[user_id]["text"]
        photo_paths = user_data[user_id]["photos"]

        # Отправляем пост в канал
        try:
            media_group = []
            for i, photo_path in enumerate(photo_paths):
                with open(photo_path, "rb") as photo:
                    if i == 0:
                        # Первое фото с текстом
                        media_group.append(InputMediaPhoto(media=photo, caption=text))
                    else:
                        # Остальные фото без текста
                        media_group.append(InputMediaPhoto(media=photo))
            
            await context.bot.send_media_group(
                chat_id=CHANNEL_ID,
                media=media_group
            )
            await query.answer("Предложка успешно отправлена")
        except Exception as e:
            logger.error(f"Ошибка при публикации предложки: {e}")
            await query.answer("Произошла ошибка при публикации предложки.")

        # Удаляем все сообщения бота
        await delete_previous_messages(context, user_id)
    elif query.data == "edit_text":
        # Устанавливаем флаг редактирования текста
        user_data[user_id]["edit_text"] = True
        await query.answer("Отправь новый текст для предложки.")
        return
    elif query.data == "cancel":
        # Уведомляем пользователя об отмене
        await query.answer("Отправка отменена.")

        # Удаляем все сообщения бота
        await delete_previous_messages(context, user_id)

        # Очищаем данные пользователя
        if user_id in user_data:
            # Удаляем сохраненные фото
            for photo_path in user_data[user_id].get("photos", []):
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            del user_data[user_id]

        # Предлагаем начать новую предложку
        await context.bot.send_message(
            chat_id=user_id,
            text="Отправка отменена.\nЕсли хотите начать новую предложку, нажмите 'Создать предложку'.",
            reply_markup=menu_keyboard
        )
        return

    # Очищаем данные пользователя
    if user_id in user_data:
        # Удаляем сохраненные фото
        for photo_path in user_data[user_id].get("photos", []):
            if os.path.exists(photo_path):
                os.remove(photo_path)
        del user_data[user_id]

    # Возвращаем меню
    await context.bot.send_message(
        chat_id=user_id,
        text="Спасибо!\nВаш пост отправлен на модерацию, теперь нужно немного подождать✨\nДля публикации так же не забудьте подписаться на наш паблик, а так же на аниме магазин KimiTo (https://t.me/kimito_64)!\nЕсли вы хотите отправить еще один пост нажмите 'создать предложку'",
        reply_markup=menu_keyboard
    )

# Основная функция
def main():
    try:
        # Укажите токен вашего бота
        application = ApplicationBuilder().token('8183574718:AAFGSr2m4izC27FseUco2iLf3Oz2Ui1FHGQ').build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))  # Обработка всех файлов
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Запускаем бота
        logger.info("Бот запущен...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    main()

