import asyncio
import logging
import sqlite3
import os
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

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
    try:
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
        # Добавляем столбец faction если его нет (для обновления схемы)
        try:
            cursor.execute("SELECT faction FROM applications LIMIT 1")
        except sqlite3.OperationalError:
            print("🔄 Добавляем столбец faction в таблицу...")
            cursor.execute('ALTER TABLE applications ADD COLUMN faction TEXT DEFAULT "refugee"')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

def add_application(user_id, username, nickname, name, age, faction="refugee"):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO applications (user_id, username, nickname, name, age, faction)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, nickname, name, age, faction))
        app_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"✅ Заявка #{app_id} добавлена для user_id {user_id}")
        return app_id
    except Exception as e:
        print(f"❌ Ошибка добавления заявки: {e}")
        return None

def update_application_status(app_id, status, admin_id=None, admin_name=None):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE applications 
        SET status = ?, admin_id = ?, admin_name = ?
        WHERE id = ?
        ''', (status, admin_id, admin_name, app_id))
        conn.commit()
        conn.close()
        print(f"✅ Статус заявки #{app_id} обновлён на {status}")
        return True
    except Exception as e:
        print(f"❌ Ошибка обновления статуса: {e}")
        return False

def delete_application(app_id):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM applications WHERE id = ?', (app_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        print(f"✅ Заявка #{app_id} удалена")
        return deleted
    except Exception as e:
        print(f"❌ Ошибка удаления заявки: {e}")
        return False

def get_application(app_id):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка получения заявки #{app_id}: {e}")
        return None

def get_user_last_application(user_id):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка получения последней заявки user_id {user_id}: {e}")
        return None

def get_pending_applications():
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE status = "pending" ORDER BY id ASC')
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
        print(f"✅ Получено {len(applications)} ожидающих заявок")
        return applications
    except Exception as e:
        print(f"❌ Ошибка получения ожидающих заявок: {e}")
        return []

def get_all_applications(limit=50, offset=0):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка получения всех заявок: {e}")
        return []

def search_applications(search_term):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM applications 
        WHERE nickname LIKE ? OR name LIKE ? OR username LIKE ? OR faction LIKE ?
        ORDER BY id DESC LIMIT 20
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
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
    except Exception as e:
        print(f"❌ Ошибка поиска заявок: {e}")
        return []

def get_stats():
    try:
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
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return 0, 0, 0, 0

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

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализируем бота и диспетчер с новым синтаксисом aiogram 3.7+
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ========== КОМАНДЫ ==========

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    logger.info(f"👤 Пользователь {user_id} (@{username}) нажал /start")
    
    # Инициализируем БД
    try:
        init_db()
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
    
    if user_id in ADMIN_IDS:
        await message.answer(
            "👑 <b>Админ-панель</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Используйте меню ниже для управления заявками:",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            "👋 <b>Добро пожаловать в бот для заявок!</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Здесь вы можете подать заявку на участие.\n"
            "Используйте кнопки ниже:",
            reply_markup=get_user_keyboard()
        )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"❌ Пользователь {message.from_user.id} попытался получить доступ к админ-панели")
        return
    
    pending = get_pending_applications()
    await message.answer(f"⏳ Ожидают рассмотрения: {len(pending)}", reply_markup=get_admin_keyboard())

# ========== ПОЛЬЗОВАТЕЛЬСКИЕ ФУНКЦИИ ==========

@dp.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"👤 Пользователь {user_id} начал подачу заявки")
    
    # Проверяем существующую заявку
    existing = get_user_last_application(user_id)
    if existing:
        if existing['status'] == 'pending':
            await message.answer(
                f"⏳ <b>У вас уже есть заявка #{existing['id']} на рассмотрении</b>\n"
                f"Ожидайте решения администратора.",
                reply_markup=get_user_keyboard()
            )
            return
        elif existing['status'] == 'approved':
            await message.answer(
                f"✅ <b>У вас уже есть одобренная заявка #{existing['id']}</b>\n"
                f"Вы не можете подать новую заявку.",
                reply_markup=get_user_keyboard()
            )
            return
    
    await message.answer(
        "✏️ <b>Введите ваш никнейм в игре:</b>\n"
        "(Минимум 2 символа, только буквы и цифры)",
        reply_markup=get_cancel_keyboard()
    )
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
    
    nickname = message.text.strip()
    if len(nickname) < 2:
        await message.answer("❌ <b>Минимум 2 символа!</b>\nВведите ваш никнейм:")
        return
    
    # Проверка на допустимые символы
    if not all(c.isalnum() or c in '_- ' for c in nickname):
        await message.answer("❌ <b>Используйте только буквы, цифры, дефисы и подчёркивания!</b>\nВведите ваш никнейм:")
        return
    
    await state.update_data(nickname=nickname)
    await message.answer(
        "📛 <b>Введите ваше реальное имя:</b>\n"
        "(Как к вам можно обращаться)",
        reply_markup=get_cancel_keyboard()
    )
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
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ <b>Минимум 2 символа!</b>\nВведите ваше имя:")
        return
    
    await state.update_data(name=name)
    await message.answer(
        "🎂 <b>Введите ваш возраст:</b>\n"
        "(От 14 до 100 лет)",
        reply_markup=get_cancel_keyboard()
    )
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
        if age < 14 or age > 100:
            await message.answer("❌ <b>Возраст должен быть от 14 до 100 лет!</b>\nВведите ваш возраст:")
            return
    except ValueError:
        await message.answer("❌ <b>Пожалуйста, введите число!</b>\nВведите ваш возраст:")
        return
    
    await state.update_data(age=age)
    await message.answer(
        "🎮 <b>Выберите фракцию:</b>\n\n"
        "⚙️ <b>Техно-Братство</b> - мастера технологий и инженерии\n"
        "🔮 <b>Орден Магов</b> - хранители древних знаний и магии\n"
        "🏕️ <b>Беженец</b> - выживальщики и путешественники\n\n"
        "Выберите одну из фракций ниже:",
        reply_markup=get_faction_keyboard()
    )
    await state.set_state(ApplicationForm.faction)

@dp.message(ApplicationForm.faction)
async def process_faction(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text == "❌ Отмена":
        await state.clear()
        if user_id in ADMIN_IDS:
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
        await message.answer("❌ <b>Пожалуйста, выберите фракцию из предложенных вариантов!</b>", reply_markup=get_faction_keyboard())
        return
    
    # Получаем все данные из состояния
    data = await state.get_data()
    nickname = data.get('nickname', '')
    name = data.get('name', '')
    age = data.get('age', 0)
    
    # Добавляем заявку в БД
    app_id = add_application(user_id, username, nickname, name, age, faction_key)
    
    if not app_id:
        await message.answer(
            "❌ <b>Произошла ошибка при сохранении заявки!</b>\n"
            "Попробуйте ещё раз или обратитесь к администратору.",
            reply_markup=get_user_keyboard()
        )
        await state.clear()
        return
    
    faction_name = FACTIONS.get(faction_key, "Неизвестно")
    
    # Отправляем подтверждение пользователю
    await message.answer(
        f"✅ <b>Заявка #{app_id} успешно подана!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Ник:</b> {nickname}\n"
        f"📛 <b>Имя:</b> {name}\n"
        f"🎂 <b>Возраст:</b> {age}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n\n"
        f"⏳ <b>Ожидайте рассмотрения администратором.</b>",
        reply_markup=get_user_keyboard()
    )
    
    logger.info(f"✅ Заявка #{app_id} подана пользователем {user_id}")
    
    # Отправляем уведомление админам
    await notify_admins_about_new_application(app_id, user_id, username, nickname, name, age, faction_name)
    
    # Очищаем состояние
    await state.clear()

async def notify_admins_about_new_application(app_id, user_id, username, nickname, name, age, faction_name):
    """Отправляет уведомление всем админам о новой заявке"""
    notification_text = (
        f"🆕 <b>У тебя новая заявочка, надо бы посмотреть!</b>\n\n"
        f"📝 <b>Заявка #{app_id}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Ник:</b> {nickname}\n"
        f"📛 <b>Имя:</b> {name}\n"
        f"🎂 <b>Возраст:</b> {age}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n"
        f"🆔 <b>ID:</b> {user_id}\n"
        f"👤 <b>Username:</b> @{username if username else 'нет'}\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"━━━━━━━━━━━━━━━━"
    )
    
    success_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                notification_text,
                reply_markup=get_application_actions(app_id)
            )
            success_count += 1
            logger.info(f"✅ Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление админу {admin_id}: {e}")
    
    logger.info(f"📨 Уведомления отправлены {success_count}/{len(ADMIN_IDS)} админам")

@dp.message(F.text == "📊 Моя заявка")
async def check_my_application(message: Message):
    user_id = message.from_user.id
    app = get_user_last_application(user_id)
    
    if not app:
        await message.answer(
            "📭 <b>У вас ещё нет заявок</b>\n"
            "Нажмите '📝 Подать заявку', чтобы создать первую заявку.",
            reply_markup=get_user_keyboard()
        )
        return
    
    # Статусы с иконками
    status_info = {
        'pending': ('⏳ <b>На рассмотрении</b>', 'Ожидайте решения администратора.'),
        'approved': ('✅ <b>Принята</b>', f'Администратор: {app["admin_name"]}' if app["admin_name"] else ''),
        'rejected': ('❌ <b>Отклонена</b>', f'Администратор: {app["admin_name"]}' if app["admin_name"] else '')
    }
    
    status_text, status_desc = status_info.get(app['status'], ('❓ <b>Неизвестный статус</b>', ''))
    faction_name = FACTIONS.get(app['faction'], "Неизвестно")
    
    await message.answer(
        f"{status_text}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Заявка #{app['id']}</b>\n"
        f"👤 <b>Ник:</b> {app['nickname']}\n"
        f"📛 <b>Имя:</b> {app['name']}\n"
        f"🎂 <b>Возраст:</b> {app['age']}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n"
        f"📅 <b>Дата:</b> {app['created_at'][:16]}\n\n"
        f"{status_desc}",
        reply_markup=get_user_keyboard()
    )

# ========== АДМИН-ФУНКЦИИ ==========

@dp.message(F.text == "📋 Новые заявки")
async def show_new_apps(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    pending = get_pending_applications()
    
    if not pending:
        await message.answer(
            "✅ <b>Нет новых заявок</b>\n"
            "Все заявки рассмотрены!",
            reply_markup=get_admin_keyboard()
        )
        return
    
    await message.answer(
        f"📋 <b>Заявок на рассмотрении:</b> {len(pending)}\n"
        f"Отправляю их по одной...",
        reply_markup=get_admin_keyboard()
    )
    
    # Отправляем каждую заявку отдельным сообщением
    for app in pending:
        try:
            faction_name = FACTIONS.get(app['faction'], "Неизвестно")
            app_text = (
                f"⏳ <b>Заявка #{app['id']}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Ник:</b> {app['nickname']}\n"
                f"📛 <b>Имя:</b> {app['name']}\n"
                f"🎂 <b>Возраст:</b> {app['age']}\n"
                f"🎮 <b>Фракция:</b> {faction_name}\n"
                f"🆔 <b>ID:</b> {app['user_id']}\n"
                f"👤 <b>Username:</b> @{app['username'] if app['username'] else 'нет'}\n"
                f"📅 <b>Дата:</b> {app['created_at'][:16]}\n"
                f"━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(
                chat_id=message.chat.id,
                text=app_text,
                reply_markup=get_application_actions(app['id'])
            )
            
            logger.info(f"📨 Заявка #{app['id']} отправлена админу {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки заявки #{app['id']}: {e}")
            await message.answer(f"❌ Ошибка отправки заявки #{app['id']}: {e}")

@dp.message(F.text == "📜 История заявок")
async def show_history(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, _, _, _ = get_stats()
    if total == 0:
        await message.answer("📭 <b>История заявок пуста</b>", reply_markup=get_admin_keyboard())
        return
    
    await show_history_page(message, 0)

async def show_history_page(message: Message, offset=0, limit=10):
    applications = get_all_applications(limit, offset)
    total, _, _, _ = get_stats()
    
    if not applications:
        await message.answer("📭 <b>Больше нет заявок</b>", reply_markup=get_admin_keyboard())
        return
    
    # Статусы с иконками
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    response = "📜 <b>История заявок</b>\n━━━━━━━━━━━━━━━━\n"
    
    for app in applications:
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        date_str = app['created_at'][:10] if app['created_at'] else '??.??.????'
        response += f"{status_icon}{faction_icon} <b>#{app['id']}</b>: {app['nickname']} ({date_str})\n"
    
    response += f"\n<b>Всего заявок:</b> {total}"
    
    await message.answer(
        response,
        reply_markup=get_history_navigation(offset, total, limit)
    )

@dp.message(F.text == "🔍 Поиск заявки")
async def start_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "🔍 <b>Поиск заявок</b>\n"
        "Введите ник, имя, username или фракцию для поиска:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SearchForm.query)

@dp.message(SearchForm.query)
async def process_search(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("✅ <b>Поиск отменён</b>", reply_markup=get_admin_keyboard())
        return
    
    search_term = message.text.strip()
    if len(search_term) < 2:
        await message.answer("❌ <b>Минимум 2 символа!</b>\nВведите запрос для поиска:")
        return
    
    results = search_applications(search_term)
    
    if not results:
        await message.answer(
            f"🔍 <b>По запросу '{search_term}' ничего не найдено</b>",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()
        return
    
    # Статусы с иконками
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    response = f"🔍 <b>Результаты поиска: '{search_term}'</b>\n━━━━━━━━━━━━━━━━\n"
    
    for app in results[:20]:  # Ограничиваем 20 результатами
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        username = f" @{app['username']}" if app['username'] else ""
        response += f"{status_icon}{faction_icon} <b>#{app['id']}</b>: {app['nickname']} ({app['name']}, {app['age']}){username}\n"
    
    if len(results) > 20:
        response += f"\n... и ещё {len(results) - 20} заявок"
    
    await message.answer(response, reply_markup=get_admin_keyboard())
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, pending, approved, rejected = get_stats()
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Всего заявок:</b> {total}\n\n"
        f"⏳ <b>На рассмотрении:</b> {pending}\n"
        f"✅ <b>Принято:</b> {approved}\n"
        f"❌ <b>Отклонено:</b> {rejected}\n\n"
        f"👑 <b>Админов:</b> {len(ADMIN_IDS)}"
    )
    
    await message.answer(stats_text, reply_markup=get_admin_keyboard())

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data.startswith("approve_"))
async def approve_app(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        app_id = int(callback.data.split("_")[1])
        app = get_application(app_id)
        
        if not app:
            await callback.answer("❌ Заявка не найдена!", show_alert=True)
            return
        
        # Обновляем статус заявки
        success = update_application_status(app_id, "approved", user_id, callback.from_user.first_name)
        
        if not success:
            await callback.answer("❌ Ошибка обновления статуса!", show_alert=True)
            return
        
        # Уведомляем пользователя
        faction_name = FACTIONS.get(app['faction'], "Неизвестно")
        try:
            await bot.send_message(
                app['user_id'],
                f"✅ <b>Ваша заявка #{app_id} одобрена!</b>\n\n"
                f"👤 <b>Ник:</b> {app['nickname']}\n"
                f"🎮 <b>Фракция:</b> {faction_name}\n"
                f"👑 <b>Администратор:</b> {callback.from_user.first_name}"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {app['user_id']}: {e}")
        
        # Обновляем сообщение с заявкой
        faction_name = FACTIONS.get(app['faction'], "Неизвестно")
        await callback.message.edit_text(
            f"✅ <b>Заявка #{app_id} одобрена</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Ник:</b> {app['nickname']}\n"
            f"📛 <b>Имя:</b> {app['name']}\n"
            f"🎮 <b>Фракция:</b> {faction_name}\n"
            f"👑 <b>Админ:</b> {callback.from_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(f"✅ Заявка #{app_id} одобрена")
        logger.info(f"✅ Админ {user_id} одобрил заявку #{app_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при одобрении заявки: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_app(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        app_id = int(callback.data.split("_")[1])
        app = get_application(app_id)
        
        if not app:
            await callback.answer("❌ Заявка не найдена!", show_alert=True)
            return
        
        # Обновляем статус заявки
        success = update_application_status(app_id, "rejected", user_id, callback.from_user.first_name)
        
        if not success:
            await callback.answer("❌ Ошибка обновления статуса!", show_alert=True)
            return
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                app['user_id'],
                f"❌ <b>Ваша заявка #{app_id} отклонена</b>\n\n"
                f"👤 <b>Ник:</b> {app['nickname']}\n"
                f"👑 <b>Администратор:</b> {callback.from_user.first_name}"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {app['user_id']}: {e}")
        
        # Обновляем сообщение с заявкой
        await callback.message.edit_text(
            f"❌ <b>Заявка #{app_id} отклонена</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Ник:</b> {app['nickname']}\n"
            f"👑 <b>Админ:</b> {callback.from_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(f"❌ Заявка #{app_id} отклонена")
        logger.info(f"❌ Админ {user_id} отклонил заявку #{app_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отклонении заявки: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("history_"))
async def navigate_history(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        offset = int(callback.data.split("_")[1])
        await show_history_page(callback.message, offset)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка навигации по истории: {e}")
        await callback.answer("❌ Ошибка навигации!", show_alert=True)

@dp.callback_query(F.data == "history_back")
async def history_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.delete()
    await show_history(callback.message)

@dp.callback_query(F.data == "page_info")
async def page_info(callback: CallbackQuery):
    await callback.answer("📄 Текущая страница")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

async def main():
    print("=" * 60)
    print("🤖 БОТ ДЛЯ ЗАЯВОК ЗАПУЩЕН")
    print("=" * 60)
    print(f"🔑 Токен бота: {BOT_TOKEN[:10]}...")
    print(f"👑 Админов: {len(ADMIN_IDS)}")
    print(f"🆔 ID админа(ов): {ADMIN_IDS}")
    print(f"📅 Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("🚀 Бот запускается...")
    print("-" * 60)
    
    # Инициализируем БД
    init_db()
    
    try:
        # Удаляем вебхук (чтобы избежать конфликта)
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Вебхук удалён")
        
        # Запускаем polling
        print("📡 Начинаем получать обновления...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Проверяем, что запущен только один экземпляр
    print("🔍 Проверка запущенных экземпляров...")
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")
