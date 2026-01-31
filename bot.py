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
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# ========== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ СРЕДЫ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "7998531124:AAFbx5wWIfX47_5vk4iyP5RR-9zs-_rq00Y")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "1336702776")
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(",")]

# Фракции для выбора
FACTIONS = {
    "techno": "⚙️ Техно-Братство",
    "mages": "🔮 Орден Магов", 
    "refugee": "🏕️ Беженец"
}

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
        faction TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        admin_id INTEGER,
        admin_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных создана")

def add_application(user_id, username, nickname, name, age, faction):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO applications (user_id, username, nickname, name, age, faction)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, nickname, name, age, faction))
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

def delete_application(app_id):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM applications WHERE id = ?', (app_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

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
            'faction': result[6], 'status': result[7], 'admin_id': result[8],
            'admin_name': result[9], 'created_at': result[10]
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
            'faction': result[6], 'status': result[7], 'admin_id': result[8],
            'admin_name': result[9], 'created_at': result[10]
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
            'faction': result[6], 'status': result[7], 'admin_id': result[8],
            'admin_name': result[9], 'created_at': result[10]
        })
    return applications

def get_all_applications(limit=50, offset=0):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
    results = cursor.fetchall()
    conn.close()
    applications = []
    for result in results:
        applications.append({
            'id': result[0], 'user_id': result[1], 'username': result[2],
            'nickname': result[3], 'name': result[4], 'age': result[5],
            'faction': result[6], 'status': result[7], 'admin_id': result[8],
            'admin_name': result[9], 'created_at': result[10]
        })
    return applications

def search_applications(search_term):
    conn = sqlite3.connect('applications.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM applications 
    WHERE nickname LIKE ? OR name LIKE ? OR username LIKE ?
    ORDER BY id DESC LIMIT 20
    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
    results = cursor.fetchall()
    conn.close()
    applications = []
    for result in results:
        applications.append({
            'id': result[0], 'user_id': result[1], 'username': result[2],
            'nickname': result[3], 'name': result[4], 'age': result[5],
            'faction': result[6], 'status': result[7], 'admin_id': result[8],
            'admin_name': result[9], 'created_at': result[10]
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
            [KeyboardButton(text="📜 История заявок")],
            [KeyboardButton(text="🔍 Поиск заявки")],
            [KeyboardButton(text="📊 Статистика")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

def get_faction_keyboard():
    builder = ReplyKeyboardBuilder()
    for faction_key, faction_name in FACTIONS.items():
        builder.add(KeyboardButton(text=faction_name))
    builder.add(KeyboardButton(text="❌ Отмена"))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_application_actions(app_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{app_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}"))
    builder.adjust(2)
    return builder.as_markup()

def get_application_detail_actions(app_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{app_id}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"history_back"))
    builder.adjust(2)
    return builder.as_markup()

def get_history_navigation(offset, total_count, limit=10):
    builder = InlineKeyboardBuilder()
    
    if offset > 0:
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"history_{offset-limit}"))
    
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit
    builder.add(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="page_info"))
    
    if offset + limit < total_count:
        builder.add(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"history_{offset+limit}"))
    
    builder.adjust(3)
    return builder.as_markup()

# ========== СОСТОЯНИЯ ==========

class ApplicationForm(StatesGroup):
    nickname = State()
    name = State()
    age = State()
    faction = State()

class SearchForm(StatesGroup):
    query = State()

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

# ========== ПОЛЬЗОВАТЕЛЬСКИЕ ФУНКЦИИ ==========

@dp.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    existing = get_user_last_application(message.from_user.id)
    if existing and existing['status'] == 'pending':
        await message.answer(f"⏳ Заявка #{existing['id']} на рассмотрении", reply_markup=get_user_keyboard())
        return
    await message.answer("✏️ Введите ваш ник (в игре):", reply_markup=get_cancel_keyboard())
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
    await message.answer("📛 Введите ваше реальное имя:")
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
    
    await state.update_data(age=age)
    await message.answer(
        "🎮 *Какую фракцию хотите выбрать?*\n\n"
        "⚙️ *Техно-Братство* - мастера технологий и инженерии\n"
        "🔮 *Орден Магов* - хранители древних знаний и магии\n"
        "🏕️ *Беженец* - выживальщики и путешественники",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_faction_keyboard()
    )
    await state.set_state(ApplicationForm.faction)

@dp.message(ApplicationForm.faction)
async def process_faction(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Отменено", reply_markup=get_admin_keyboard())
        else:
            await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    # Определяем выбранную фракцию
    faction_key = None
    for key, name in FACTIONS.items():
        if message.text == name:
            faction_key = key
            break
    
    if not faction_key:
        await message.answer("❌ Выберите фракцию из предложенных вариантов:", reply_markup=get_faction_keyboard())
        return
    
    data = await state.get_data()
    app_id = add_application(
        message.from_user.id, 
        message.from_user.username, 
        data['nickname'], 
        data['name'], 
        data['age'], 
        faction_key
    )
    
    faction_name = FACTIONS.get(faction_key, "Неизвестно")
    
    await message.answer(
        f"✅ Заявка #{app_id} подана!\n"
        f"🎮 Фракция: {faction_name}\n"
        f"⏳ Ожидайте рассмотрения администратором.",
        reply_markup=get_user_keyboard()
    )
    
    # Уведомление админам
    app_text = f"""
🆕 *У тебя новая заявочка, надо бы посмотреть!*

📝 *Заявка #{app_id}!*
👤 Ник: {data['nickname']}
📛 Имя: {data['name']}
🎂 Возраст: {data['age']}
🎮 Фракция: {faction_name}
🆔 ID: {message.from_user.id}
👤 Username: @{message.from_user.username or 'Нет'}
📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}
    """.strip()
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                app_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_application_actions(app_id)
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления админу {admin_id}: {e}")
    
    await state.clear()

@dp.message(F.text == "📊 Моя заявка")
async def check_my_application(message: Message):
    app = get_user_last_application(message.from_user.id)
    if not app:
        await message.answer("📭 Нет заявок", reply_markup=get_user_keyboard())
        return
    
    status_icons = {
        'pending': '⏳ На рассмотрении',
        'approved': '✅ Принята',
        'rejected': '❌ Отклонена'
    }
    
    status_text = status_icons.get(app['status'], '❓ Неизвестно')
    admin_info = f"\n👑 Рассмотрел: {app['admin_name']}" if app['admin_name'] else ""
    faction_name = FACTIONS.get(app['faction'], "Неизвестно")
    
    response = f"""
{status_text}
━━━━━━━━━━━━━━━━
📝 *Заявка #{app['id']}*
👤 Ник: {app['nickname']}
📛 Имя: {app['name']}
🎂 Возраст: {app['age']}
🎮 Фракция: {faction_name}
📅 Дата: {app['created_at'][:16]}
{admin_info}
    """.strip()
    
    await message.answer(response, parse_mode=ParseMode.MARKDOWN, reply_markup=get_user_keyboard())

# ========== АДМИН-ФУНКЦИИ ==========

@dp.message(F.text == "📋 Новые заявки")
async def show_new_apps(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    pending = get_pending_applications()
    
    if not pending:
        await message.answer("✅ Нет новых заявок", reply_markup=get_admin_keyboard())
        return
    
    await message.answer(f"📋 Заявок на рассмотрении: {len(pending)}", reply_markup=get_admin_keyboard())
    
    # Отправляем все заявки по одной
    for app in pending:
        try:
            faction_name = FACTIONS.get(app['faction'], "Неизвестно")
            app_text = f"""
⏳ *Заявка #{app['id']}*
━━━━━━━━━━━━━━━━
👤 Ник: {app['nickname']}
📛 Имя: {app['name']}
🎂 Возраст: {app['age']}
🎮 Фракция: {faction_name}
🆔 ID: {app['user_id']}
👤 Username: @{app['username'] or 'Нет'}
📅 Дата: {app['created_at'][:16]}
━━━━━━━━━━━━━━━━
            """.strip()
            
            await bot.send_message(
                chat_id=message.chat.id,
                text=app_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_application_actions(app['id'])
            )
            
        except Exception as e:
            print(f"❌ Ошибка при отправке заявки #{app['id']}: {e}")

@dp.message(F.text == "📜 История заявок")
async def show_history(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, _, _, _ = get_stats()
    if total == 0:
        await message.answer("📭 История заявок пуста", reply_markup=get_admin_keyboard())
        return
    
    await show_history_page(message, 0)

async def show_history_page(message: Message, offset=0, limit=10):
    applications = get_all_applications(limit, offset)
    total, _, _, _ = get_stats()
    
    if not applications:
        await message.answer("📭 Больше нет заявок", reply_markup=get_admin_keyboard())
        return
    
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    response = f"📜 *История заявок*\n━━━━━━━━━━━━━━━━\n"
    
    for app in applications:
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        response += f"{status_icon}{faction_icon} #{app['id']}: {app['nickname']} ({app['name']})\n"
    
    response += f"\nВсего заявок: {total}"
    
    await message.answer(
        response,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_history_navigation(offset, total, limit)
    )

@dp.message(F.text == "🔍 Поиск заявки")
async def start_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer("🔍 Введите ник, имя или username для поиска:", reply_markup=get_back_keyboard())
    await state.set_state(SearchForm.query)

@dp.message(SearchForm.query)
async def process_search(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("✅ Поиск отменён", reply_markup=get_admin_keyboard())
        return
    
    search_term = message.text.strip()
    if len(search_term) < 2:
        await message.answer("❌ Минимум 2 символа:")
        return
    
    results = search_applications(search_term)
    
    if not results:
        await message.answer(f"🔍 По запросу '{search_term}' ничего не найдено", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    response = f"🔍 *Результаты поиска: '{search_term}'*\n━━━━━━━━━━━━━━━━\n"
    
    for app in results[:20]:  # Ограничиваем 20 результатами
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        username = f" @{app['username']}" if app['username'] else ""
        response += f"{status_icon}{faction_icon} #{app['id']}: {app['nickname']} ({app['name']}, {app['age']}){username}\n"
    
    if len(results) > 20:
        response += f"\n... и ещё {len(results) - 20} заявок"
    
    await message.answer(response, parse_mode=ParseMode.MARKDOWN, reply_markup=get_admin_keyboard())
    await state.clear()

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

# ========== CALLBACK ОБРАБОТЧИКИ ==========

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
            faction_name = FACTIONS.get(app['faction'], "Неизвестно")
            await bot.send_message(
                app['user_id'], 
                f"✅ Заявка #{app_id} одобрена!\n"
                f"🎮 Ваша фракция: {faction_name}\n"
                f"👑 Администратор: {callback.from_user.first_name}"
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления пользователю: {e}")
    
    # Обновляем сообщение с заявкой
    faction_name = FACTIONS.get(app['faction'], "Неизвестно") if app else "Неизвестно"
    
    try:
        await callback.message.edit_text(
            f"✅ *Заявка #{app_id} одобрена*\n"
            f"👑 Админ: {callback.from_user.first_name}\n"
            f"🎮 Фракция: {faction_name}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        await callback.answer("✅ Одобрено")
    
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
            await bot.send_message(
                app['user_id'], 
                f"❌ Заявка #{app_id} отклонена\n"
                f"👑 Администратор: {callback.from_user.first_name}"
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления пользователю: {e}")
    
    try:
        await callback.message.edit_text(
            f"❌ *Заявка #{app_id} отклонена*\n"
            f"👑 Админ: {callback.from_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        await callback.answer("❌ Отклонено")
    
    await callback.answer("❌ Отклонено")

@dp.callback_query(F.data.startswith("delete_"))
async def delete_app(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    app_id = int(callback.data.split("_")[1])
    app = get_application(app_id)
    
    if not app:
        await callback.answer("❌ Заявка не найдена!")
        return
    
    # Запрашиваем подтверждение
    faction_name = FACTIONS.get(app['faction'], "Неизвестно")
    confirm_text = f"""
⚠️ *Подтверждение удаления*
━━━━━━━━━━━━━━━━
📝 Заявка #{app_id}
👤 Ник: {app['nickname']}
📛 Имя: {app['name']}
🎂 Возраст: {app['age']}
🎮 Фракция: {faction_name}
🆔 ID: {app['user_id']}

❓ Вы уверены, что хотите удалить эту заявку?
    """.strip()
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{app_id}"))
    builder.add(InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete"))
    builder.adjust(2)
    
    try:
        await callback.message.edit_text(confirm_text, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(confirm_text, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup())
    
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_app(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    app_id = int(callback.data.split("_")[2])
    
    if delete_application(app_id):
        try:
            await callback.message.edit_text(f"🗑️ Заявка #{app_id} удалена")
        except:
            await callback.message.answer(f"🗑️ Заявка #{app_id} удалена")
        await callback.answer("✅ Удалено")
    else:
        try:
            await callback.message.edit_text(f"❌ Ошибка при удалении заявки #{app_id}")
        except:
            await callback.message.answer(f"❌ Ошибка при удалении заявки #{app_id}")
        await callback.answer("❌ Ошибка")

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await callback.message.delete()
    await callback.answer("❌ Удаление отменено")

@dp.callback_query(F.data.startswith("history_"))
async def navigate_history(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        offset = int(callback.data.split("_")[1])
        await show_history_page(callback.message, offset)
        await callback.answer()
    except:
        await callback.answer("❌ Ошибка навигации")

@dp.callback_query(F.data == "history_back")
async def history_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!")
        return
    
    await callback.message.delete()
    await show_history(callback.message)

@dp.callback_query(F.data == "page_info")
async def page_info(callback: CallbackQuery):
    await callback.answer("Текущая страница")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

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
    asyncio.run(main())
