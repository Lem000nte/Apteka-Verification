import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ===== НАСТРОЙКИ =====
CHAT_ID = -1001234567890 # ID супергруппы
TOKEN = 1234567890 # Токен
ADMIN_IDS = {} # замените на ID админов

# Файл для хранения забаненных пользователей
BANNED_FILE = "banned_users.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== РАБОТА С БАНАМИ =====
def load_banned() -> set:
    """Загружает множество ID забаненных пользователей из файла."""
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data)
    return set()

def save_banned(banned_set: set) -> None:
    """Сохраняет множество забаненных ID в файл."""
    with open(BANNED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(banned_set), f, ensure_ascii=False, indent=2)

# Глобальное множество забаненных пользователей
BANNED_USERS = load_banned()

# Текст с приветсвием
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
'''
Привет, напиши заявку для вступления в нашу дружную семью АптекаПикс, и мы скоро проверим её.

У нас ко вступлению относятся строго, поэтому не указывайте ложную информацию:

1. Когда вы можете тапать и в какие дни? (Например: от 16:00 до 23:00 по киеву, в выходные)
2. Есть ли у вас навыки помимо тапанья?(Рисование артов, написание кода и.д)
3. Сколько вы в пискелях(лет или месяцев. Например: с мая 2024)
4. Откуда вы про нас узнали? (Посоветовали друзья, тикток и т.д)
5. В каких вы сейчас фракциях состоите(!), или в каких состояли

Скоро лично глава фракции осмотрит вашу заявку и либо примет либо отклонит заявку.

ПОМНИТЕ! нам нужны любые люди, которые могут тапать регулярно.
'''
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    # Проверяем, не забанен ли пользователь
    if user_id in BANNED_USERS:
        await update.message.reply_text("🚫 Вы забанены в боте и не можете отправлять заявки.")
        return

    if user_id in ADMIN_IDS:
        await update.message.reply_text("Вы администратор, заявки от вас не принимаются.")
        return

    text = update.message.text
    username = user.username or "без username"

    admin_text = (
        f"📩 Новая заявка от @{username} (ID: <code>{user_id}</code>):\n\n{text}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌", callback_data=f"reject_{user_id}"),
            InlineKeyboardButton("🚫", callback_data=f"ban_{user_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    await update.message.reply_text("Ваша заявка отправлена.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admin = update.effective_user
    if admin.id not in ADMIN_IDS:
        await query.answer("⛔ Вы не админ", show_alert=True)
        return

    data = query.data
    action, user_id_str = data.split("_")
    user_id = int(user_id_str)

    try:
        if action == "approve":
            try:
                # Создаём одноразовую ссылку-приглашение
                invite_link_obj = await context.bot.create_chat_invite_link(
                    chat_id=CHAT_ID,
                    member_limit=1,
                )
                link = invite_link_obj.invite_link
                # Отправляем ссылку пользователю
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Ваша заявка одобрена!\nСсылка для вступления:\n{link}\nДобро пожаловать в Аптека пикс. теперь вы часть нашей большой семьи.",
                )
                # Обновляем сообщение у админа
                new_text = query.message.text + f"\n\n✅ Одобрено администратором @{admin.username}"
                await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=None)
            except Exception as e:
                logger.error(f"Ошибка при создании ссылки: {e}")
                error_text = query.message.text + "\n\n⚠️ Ошибка: недостаточно прав для создания ссылки. Проверьте права бота."
                await query.edit_message_text(text=error_text, parse_mode="HTML", reply_markup=None)
                await query.answer("Ошибка прав бота.", show_alert=True)

        elif action == "reject":
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Ваша заявка была отклонена. Попробуйте чуть позже",
            )
            new_text = query.message.text + f"\n\n❌ Отклонено администратором @{admin.username}"
            await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=None)

        elif action == "ban":
            # Добавляем пользователя в бан
            BANNED_USERS.add(user_id)
            save_banned(BANNED_USERS)
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🚫 Вы были забанены в боте за нарушение правил. Ваши заявки больше не принимаются.",
                )
            except Exception:
                logger.warning(f"Не удалось отправить сообщение забаненному пользователю {user_id} (возможно, он не начал диалог).")
            # Обновляем сообщение у админа
            new_text = query.message.text + f"\n\n🚫 Пользователь забанен администратором @{admin.username}"
            await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=None)
            await query.answer("Пользователь забанен.", show_alert=True)

        else:
            await query.answer("Неизвестное действие.")

    except Exception as e:
        logger.error(f"Общая ошибка: {e}")
        await query.edit_message_text(
            text=query.message.text + "\n\n⚠️ Произошла ошибка.",
            reply_markup=None
        )


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /unban <user_id> — разбан пользователя."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только администраторы могут разбанивать.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /unban <ID пользователя>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return

    if user_id in BANNED_USERS:
        BANNED_USERS.remove(user_id)
        save_banned(BANNED_USERS)
        await update.message.reply_text(f"✅ Пользователь с ID {user_id} разбанен.")
        # Попытаемся уведомить пользователя
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ваш бан в боте снят. Теперь вы снова можете отправлять заявки.",
            )
        except Exception:
            logger.warning(f"Не удалось уведомить о разбане пользователя {user_id}.")
    else:
        await update.message.reply_text(f"ℹ️ Пользователь с ID {user_id} не находится в бане.")


def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling()


if __name__ == "__main__":
    main()