import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

# ========== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ СРЕДЫ ==========
# Railway автоматически подставит значения
BOT_TOKEN = os.getenv("BOT_TOKEN", "7998531124:AAFbx5wWIfX47_5vk4iyP5RR-9zs-_rq00Y")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "1336702776")
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(",")]

# ========== БАЗА ДАННЫХ ==========

def init_db():
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        nickname TEXT NOT NULL,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        admin_id INTEGER,
        admin_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных создана")

def add_application(user_id, username, nickname, name, age):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO applications (user_id, username, nickname, name, age)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, nickname, name, age))
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return app_id

def update_application_status(app_id, status, admin_id=None, admin_name=None):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE applications 
    SET status = ?, admin_id = ?, admin_name = ?
    WHERE id = ?
    ''', (status, admin_id, admin_name, app_id))
    conn.commit()
    conn.close()

def get_application(app_id):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'id': result[0], 'user_id': result[1], 'username': result[2],
            'nickname': result[3], 'name': result[4], 'age': result[5],
            'status': result[6], 'admin_id': result[7], 'admin_name': result[8],
            'created_at': result[9]
        }
    return None

def get_user_last_application(user_id):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'id': result[0], 'user_id': result[1], 'username': result[2],
            'nickname': result[3], 'name': result[4], 'age': result[5],
            'status': result[6], 'admin_id': result[7], 'admin_name': result[8],
            'created_at': result[9]
        }
    return None

def get_pending_applications():
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications WHERE status = "pending" ORDER BY id DESC')
    results = cursor.fetchall()
    conn.close()
    applications = []
    for result in results:
        applications.append({
            'id': result[0], 'user_id': result[1], 'username': result[2],
            'nickname': result[3], 'name': result[4], 'age': result[5],
            'status': result[6], 'admin_id': result[7], 'admin_name': result[8],
            'created_at': result[9]
        })
    return applications

def get_stats():
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM applications")
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'pending'")
    pending = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'approved'")
    approved = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'rejected'")
    rejected = cursor.fetchone()[0] or 0
    conn.close()
    return total, pending, approved, rejected

# ========== КЛАВИАТУРЫ ==========

def get_user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать заявку")],
            [KeyboardButton(text="📊 Моя заявка")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Новые заявки")],
            [KeyboardButton(text="📊 Статистика")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_application_actions(app_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{app_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}"))
    builder.adjust(2)
    return builder.as_markup()

# ========== СОСТОЯНИЯ ==========

class ApplicationForm(StatesGroup):
    nickname = State()
    name = State()
    age = State()

# ========== БОТ ==========

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: Message):
    init_db()
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👑 Админ-панель", reply_markup=get_admin_keyboard())
    else:
        await message.answer("👋 Бот для заявок", reply_markup=get_user_keyboard())

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    pending = get_pending_applications()
    await message.answer(f"⏳ Ожидают: {len(pending)}", reply_markup=get_admin_keyboard())

@dp.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    existing = get_user_last_application(message.from_user.id)
    if existing and existing['status'] == 'pending':
        await message.answer(f"⏳ Заявка #{existing['id']} на рассмотрении", reply_markup=get_user_keyboard())
        return
    await message.answer("✏️ Введите ваш ник:", reply_markup=get_cancel_keyboard())
    await state.set_state(ApplicationForm.nickname)

@dp.message(ApplicationForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Отменено", reply_markup=get_admin_keyboard())
        else:
            await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    if len(message.text) < 2:
        await message.answer("❌ Минимум 2 символа:")
        return
    await state.update_data(nickname=message.text.strip())
    await message.answer("📛 Введите ваше имя:")
    await state.set_state(ApplicationForm.name)

@dp.message(ApplicationForm.name)
async def process_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Отменено", reply_markup=get_admin_keyboard())
        else:
            await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    if len(message.text) < 2:
        await message.answer("❌ Минимум 2 символа:")
        return
    await state.update_data(name=message.text.strip())
    await message.answer("🎂 Введите ваш возраст:")
    await state.set_state(ApplicationForm.age)

@dp.message(ApplicationForm.age)
async def process_age(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Отменено", reply_markup=get_admin_keyboard())
        else:
            await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    try:
        age = int(message.text.strip())
        if age < 10 or age > 100:
            await message.answer("❌ Возраст 10-100 лет:")
            return
    except:
        await message.answer("❌ Введите число:")
        return
    
    data = await state.get_data()
    app_id = add_application(message.from_user.id, message.from_user.username, data['nickname'], data['name'], age)
    
    await message.answer(f"✅ Заявка #{app_id} подана!", reply_markup=get_user_keyboard())
    
    # Уведомление админам
    app_text = f"""
🆕 *НОВАЯ ЗАЯВКА #{app_id}!*
👤 Ник: {data['nickname']}
📛 Имя: {data['name']}
🎂 Возраст: {age}
🆔 ID: {message.from_user.id}
    """.strip()
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                app_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_application_actions(app_id)
            )
        except:
            pass
    
    await state.clear()

@dp.message(F.text == "📊 Моя заявка")
async def check_my_application(message: Message):
    app = get_user_last_application(message.from_user.id)
    if not app:
        await message.answer("📭 Нет заявок", reply_markup=get_user_keyboard())
        return
    status = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(app['status'], '❓')
    await message.answer(f"{status} Заявка #{app['id']}\n👤 {app['nickname']}\n📛 {app['name']}\n🎂 {app['age']}")

@dp.message(F.text == "📋 Новые заявки")
async def show_new_apps(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    pending = get_pending_applications()
    
    if not pending:
        await message.answer("✅ Нет заявок", reply_markup=get_admin_keyboard())
        return
    
    await message.answer(f"📋 Заявок на рассмотрении: {len(pending)}", reply_markup=get_admin_keyboard())
    
    for app in pending[:3]:
        try:
            app_text = f"""
⏳ *Заявка #{app['id']}*
👤 Ник: {app['nickname']}
📛 Имя: {app['name']}
🎂 Возраст: {app['age']}
🆔 ID: {app['user_id']}
            """.strip()
            
            await bot.send_message(
                chat_id=message.chat.id,
                text=app_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_application_actions(app['id'])
            )
            
        except Exception as e:
            print(f"Ошибка при отправке заявки: {e}")

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, pending, approved, rejected = get_stats()
    
    stats_text = f"""
📊 Статистика бота
━━━━━━━━━━━━━━━━
📋 Всего заявок: *{total}*

⏳ На рассмотрении: *{pending}*
✅ Принято: *{approved}*
❌ Отклонено: *{rejected}*

👑 Админов: *{len(ADMIN_IDS)}*
    """.strip()
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_admin_keyboard())

@dp.callback_query(F.data.startswith("approve_"))
async def approve_app(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    app_id = int(callback.data.split("_")[1])
    update_application_status(app_id, "approved", callback.from_user.id, callback.from_user.first_name)
    app = get_application(app_id)
    if app:
        try:
            await bot.send_message(app['user_id'], f"✅ Заявка #{app_id} одобрена!")
        except:
            pass
    await callback.message.edit_text(f"✅ Заявка #{app_id} одобрена")
    await callback.answer("✅ Одобрено")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_app(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    app_id = int(callback.data.split("_")[1])
    update_application_status(app_id, "rejected", callback.from_user.id, callback.from_user.first_name)
    app = get_application(app_id)
    if app:
        try:
            await bot.send_message(app['user_id'], f"❌ Заявка #{app_id} отклонена")
        except:
            pass
    await callback.message.edit_text(f"❌ Заявка #{app_id} отклонена")
    await callback.answer("❌ Отклонено")

async def main():
    print("=" * 50)
    print("🤖 БОТ ДЛЯ ЗАЯВОК ЗАПУЩЕН НА RAILWAY")
    print("=" * 50)
    print(f"👑 Админов: {len(ADMIN_IDS)}")
    print(f"🆔 ID админа(ов): {ADMIN_IDS}")
    print("🚀 Бот запускается...")
    print("Нажмите Ctrl+C для остановки")
    print("-" * 50)
    
    # Инициализируем БД
    init_db()
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
