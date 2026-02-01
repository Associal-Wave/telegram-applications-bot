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

# Фракции для выбора (без беженцев)
FACTIONS = {
    "techno": "⚙️ Техно-Братство",
    "mages": "🔮 Орден Магов"
}

# ========== ПРИВЕТСТВИЕ ==========
WELCOME_MESSAGE = """<b>ПРОТОКОЛ ППЧ
Версия: Assonex - v.1.0</b>

<code>> СКАНИРОВАНИЕ ОКРУЖАЮЩЕЙ РЕАЛЬНОСТИ...
> ОБНАРУЖЕНО: Слияние магических и технологических полей.
> АКСИОМА МИРА: Единство рождается из Противостояния.</code>

Голос неизвестного меха взывает к тебе, он состоит из плоти.. Магии.. Металла.. Ему надо знать кто ты, какой путь ты выберешь. Так сделай же свой выбор и начни свою историю в мире, где магия и технологии живут в хрупком равновесии, хоть и равновесие держится на вечном противостоянии.

<b>Ваша цель:</b> Войти в систему. Найти свою фракцию - Орден магов или Техно-Братство.
━━━━━━━━━━━━━━━━"""

# ========== БАЗА ДАННЫХ ==========

def init_db():
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Таблица заявок
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
        
        # Таблица жалоб (книга жалоб)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            reported_user TEXT NOT NULL,
            complaint_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER,
            admin_name TEXT,
            resolution_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
        ''')
        
        # Проверяем и добавляем столбец faction если его нет
        try:
            cursor.execute("SELECT faction FROM applications LIMIT 1")
        except sqlite3.OperationalError:
            print("🔄 Добавляем столбец faction в таблицу...")
            cursor.execute('ALTER TABLE applications ADD COLUMN faction TEXT DEFAULT "techno"')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

# ========== ФУНКЦИИ ДЛЯ ЗАЯВОК ==========

def add_application(user_id, username, nickname, name, age, faction="techno"):
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

# ========== ФУНКЦИИ ДЛЯ ЖАЛОБ ==========

def add_complaint(user_id, username, reported_user, complaint_text):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO complaints (user_id, username, reported_user, complaint_text)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, reported_user, complaint_text))
        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"✅ Жалоба #{complaint_id} добавлена от user_id {user_id}")
        return complaint_id
    except Exception as e:
        print(f"❌ Ошибка добавления жалобы: {e}")
        return None

def update_complaint_status(complaint_id, status, admin_id=None, admin_name=None, resolution_text=None):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        
        if status == 'resolved':
            cursor.execute('''
            UPDATE complaints 
            SET status = ?, admin_id = ?, admin_name = ?, resolution_text = ?, resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (status, admin_id, admin_name, resolution_text, complaint_id))
        else:
            cursor.execute('''
            UPDATE complaints 
            SET status = ?, admin_id = ?, admin_name = ?
            WHERE id = ?
            ''', (status, admin_id, admin_name, complaint_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Статус жалобы #{complaint_id} обновлён на {status}")
        return True
    except Exception as e:
        print(f"❌ Ошибка обновления жалобы: {e}")
        return False

def get_complaint(complaint_id):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                'id': result[0], 'user_id': result[1], 'username': result[2],
                'reported_user': result[3], 'complaint_text': result[4],
                'status': result[5], 'admin_id': result[6], 'admin_name': result[7],
                'resolution_text': result[8], 'created_at': result[9],
                'resolved_at': result[10]
            }
        return None
    except Exception as e:
        print(f"❌ Ошибка получения жалобы #{complaint_id}: {e}")
        return None

def get_pending_complaints():
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE status = "pending" ORDER BY id ASC')
        results = cursor.fetchall()
        conn.close()
        complaints = []
        for result in results:
            complaints.append({
                'id': result[0], 'user_id': result[1], 'username': result[2],
                'reported_user': result[3], 'complaint_text': result[4],
                'status': result[5], 'admin_id': result[6], 'admin_name': result[7],
                'resolution_text': result[8], 'created_at': result[9],
                'resolved_at': result[10]
            })
        return complaints
    except Exception as e:
        print(f"❌ Ошибка получения ожидающих жалоб: {e}")
        return []

def get_all_complaints(limit=50, offset=0):
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
        results = cursor.fetchall()
        conn.close()
        complaints = []
        for result in results:
            complaints.append({
                'id': result[0], 'user_id': result[1], 'username': result[2],
                'reported_user': result[3], 'complaint_text': result[4],
                'status': result[5], 'admin_id': result[6], 'admin_name': result[7],
                'resolution_text': result[8], 'created_at': result[9],
                'resolved_at': result[10]
            })
        return complaints
    except Exception as e:
        print(f"❌ Ошибка получения всех жалоб: {e}")
        return []

def get_complaints_stats():
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM complaints")
        total = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'pending'")
        pending = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'reviewing'")
        reviewing = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'resolved'")
        resolved = cursor.fetchone()[0] or 0
        conn.close()
        return total, pending, reviewing, resolved
    except Exception as e:
        print(f"❌ Ошибка получения статистики жалоб: {e}")
        return 0, 0, 0, 0

# ========== КЛАВИАТУРЫ ==========

def get_user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать заявку")],
            [KeyboardButton(text="📊 Моя заявка")],
            [KeyboardButton(text="📖 Книга жалоб")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Новые заявки")],
            [KeyboardButton(text="📜 История заявок")],
            [KeyboardButton(text="📖 Жалобы")],
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
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_application_actions(app_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{app_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}"))
    builder.adjust(2)
    return builder.as_markup()

def get_complaint_actions(complaint_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👁️ Просмотр", callback_data=f"view_complaint_{complaint_id}"))
    builder.add(InlineKeyboardButton(text="✅ Решено", callback_data=f"resolve_complaint_{complaint_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_complaint_{complaint_id}"))
    builder.adjust(2, 1)
    return builder.as_markup()

def get_complaint_detail_actions(complaint_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Решено", callback_data=f"resolve_complaint_{complaint_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_complaint_{complaint_id}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"complaints_back"))
    builder.adjust(2, 1)
    return builder.as_markup()

def get_history_navigation(offset, total_count, limit=10, prefix="history"):
    builder = InlineKeyboardBuilder()
    
    if offset > 0:
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}_{offset-limit}"))
    
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit
    builder.add(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="page_info"))
    
    if offset + limit < total_count:
        builder.add(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"{prefix}_{offset+limit}"))
    
    builder.adjust(3)
    return builder.as_markup()

# ========== СОСТОЯНИЯ ==========

class ApplicationForm(StatesGroup):
    nickname = State()
    name = State()
    age = State()
    faction = State()

class ComplaintForm(StatesGroup):
    reported_user = State()
    complaint_text = State()

class ResolutionForm(StatesGroup):
    resolution_text = State()

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

# ========== ОСНОВНЫЕ КОМАНДЫ С ПРИВЕТСТВИЕМ ==========

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
    
    # Отправляем приветственное сообщение
    await message.answer(WELCOME_MESSAGE)
    
    # Небольшая задержка для эффекта
    await asyncio.sleep(1)
    
    if user_id in ADMIN_IDS:
        await message.answer(
            "👑 <b>Админ-панель</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Используйте меню ниже для управления заявками и жалобами:",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            "🎮 <b>Система готова к приёму вашей заявки</b>\n\n"
            "<i>Выберите действие в меню ниже:</i>",
            reply_markup=get_user_keyboard()
        )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"❌ Пользователь {message.from_user.id} попытался получить доступ к админ-панели")
        return
    
    pending_apps = get_pending_applications()
    pending_complaints = get_pending_complaints()
    
    await message.answer(
        f"👑 <b>Админ-панель</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>Ожидают заявок:</b> {len(pending_apps)}\n"
        f"📖 <b>Жалоб на рассмотрении:</b> {len(pending_complaints)}",
        reply_markup=get_admin_keyboard()
    )

# ========== КНИГА ЖАЛОБ (ПОЛЬЗОВАТЕЛИ) ==========

@dp.message(F.text == "📖 Книга жалоб")
async def start_complaint(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"👤 Пользователь {user_id} начал оформление жалобы")
    
    await message.answer(
        "📖 <b>Книга жалоб</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Здесь вы можете оставить жалобу на другого игрока.\n\n"
        "✏️ <b>Введите никнейм игрока, на которого хотите пожаловаться:</b>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ComplaintForm.reported_user)

@dp.message(ComplaintForm.reported_user)
async def process_reported_user(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    reported_user = message.text.strip()
    if len(reported_user) < 2:
        await message.answer("❌ <b>Минимум 2 символа!</b>\nВведите никнейм игрока:")
        return
    
    await state.update_data(reported_user=reported_user)
    await message.answer(
        "📝 <b>Опишите проблему:</b>\n"
        "(Что произошло, когда, подробное описание ситуации)\n\n"
        "<i>Старайтесь описывать максимально подробно и объективно.</i>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ComplaintForm.complaint_text)

@dp.message(ComplaintForm.complaint_text)
async def process_complaint_text(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("✅ Отменено", reply_markup=get_user_keyboard())
        return
    
    complaint_text = message.text.strip()
    if len(complaint_text) < 10:
        await message.answer("❌ <b>Слишком короткое описание!</b>\nОпишите проблему подробнее (минимум 10 символов):")
        return
    
    data = await state.get_data()
    reported_user = data.get('reported_user', '')
    
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Добавляем жалобу в БД
    complaint_id = add_complaint(user_id, username, reported_user, complaint_text)
    
    if not complaint_id:
        await message.answer(
            "❌ <b>Произошла ошибка при сохранении жалобы!</b>\n"
            "Попробуйте ещё раз или обратитесь к администратору.",
            reply_markup=get_user_keyboard()
        )
        await state.clear()
        return
    
    await message.answer(
        f"✅ <b>Жалоба #{complaint_id} успешно отправлена!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>На кого:</b> {reported_user}\n"
        f"📝 <b>Ваша жалоба:</b> {complaint_text[:100]}...\n\n"
        f"⏳ <b>Администраторы рассмотрят вашу жалобу в ближайшее время.</b>\n"
        f"Вы получите уведомление, когда жалоба будет рассмотрена.",
        reply_markup=get_user_keyboard()
    )
    
    logger.info(f"✅ Жалоба #{complaint_id} отправлена пользователем {user_id}")
    await state.clear()

# ========== АДМИН-ФУНКЦИИ ДЛЯ ЖАЛОБ ==========

@dp.message(F.text == "📖 Жалобы")
async def show_complaints_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, pending, reviewing, resolved = get_complaints_stats()
    
    menu_text = (
        "📖 <b>Управление жалобами</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Статистика:</b>\n"
        f"⏳ Ожидают: {pending}\n"
        f"👁️ На рассмотрении: {reviewing}\n"
        f"✅ Решено: {resolved}\n"
        f"📋 Всего: {total}\n\n"
        "Выберите действие:\n"
        "1. Нажмите на жалобу для просмотра\n"
        "2. Используйте кнопки под жалобами"
    )
    
    await message.answer(menu_text, reply_markup=get_admin_keyboard())
    
    # Показываем ожидающие жалобы
    pending_complaints = get_pending_complaints()
    
    if not pending_complaints:
        await message.answer("✅ <b>Нет новых жалоб</b>\nВсе жалобы рассмотрены!")
        return
    
    for complaint in pending_complaints[:5]:  # Показываем первые 5
        try:
            complaint_text_preview = complaint['complaint_text']
            if len(complaint_text_preview) > 100:
                complaint_text_preview = complaint_text_preview[:100] + "..."
            
            complaint_text = (
                f"📖 <b>Жалоба #{complaint['id']}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 <b>От:</b> @{complaint['username'] if complaint['username'] else 'нет'} (ID: {complaint['user_id']})\n"
                f"⚠️ <b>На кого:</b> {complaint['reported_user']}\n"
                f"📅 <b>Дата:</b> {complaint['created_at'][:16]}\n"
                f"📝 <b>Жалоба:</b> {complaint_text_preview}\n"
                f"━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(
                chat_id=message.chat.id,
                text=complaint_text,
                reply_markup=get_complaint_actions(complaint['id'])
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки жалобы #{complaint['id']}: {e}")

@dp.callback_query(F.data.startswith("view_complaint_"))
async def view_complaint_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        complaint_id = int(callback.data.split("_")[2])
        complaint = get_complaint(complaint_id)
        
        if not complaint:
            await callback.answer("❌ Жалоба не найдена!", show_alert=True)
            return
        
        # Обновляем статус на "reviewing" если ещё не просмотрена
        if complaint['status'] == 'pending':
            update_complaint_status(complaint_id, 'reviewing', callback.from_user.id, callback.from_user.first_name)
        
        complaint_text = (
            f"📖 <b>Жалоба #{complaint['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>От кого:</b> @{complaint['username'] if complaint['username'] else 'нет'}\n"
            f"🆔 <b>ID отправителя:</b> {complaint['user_id']}\n"
            f"⚠️ <b>На кого жалуется:</b> {complaint['reported_user']}\n"
            f"📅 <b>Дата подачи:</b> {complaint['created_at'][:16]}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Текст жалобы:</b>\n"
            f"{complaint['complaint_text']}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Статус:</b> {complaint['status']}"
        )
        
        await callback.message.edit_text(
            complaint_text,
            reply_markup=get_complaint_detail_actions(complaint_id)
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка просмотра жалобы: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("resolve_complaint_"))
async def resolve_complaint(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        complaint_id = int(callback.data.split("_")[2])
        
        # Сохраняем ID жалобы в состоянии
        await state.update_data(complaint_id=complaint_id)
        
        await callback.message.answer(
            "✅ <b>Решение жалобы</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Введите текст решения или описание действий, предпринятых по жалобе:",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(ResolutionForm.resolution_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка начала решения жалобы: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.message(ResolutionForm.resolution_text)
async def process_resolution_text(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Отменено", reply_markup=get_admin_keyboard())
        return
    
    resolution_text = message.text.strip()
    if len(resolution_text) < 5:
        await message.answer("❌ <b>Слишком короткий текст!</b>\nВведите подробное описание решения:")
        return
    
    data = await state.get_data()
    complaint_id = data.get('complaint_id')
    
    if not complaint_id:
        await message.answer("❌ <b>Ошибка: не найден ID жалобы</b>", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    
    # Обновляем статус жалобы
    success = update_complaint_status(
        complaint_id, 
        'resolved', 
        message.from_user.id, 
        message.from_user.first_name,
        resolution_text
    )
    
    if not success:
        await message.answer("❌ <b>Ошибка при обновлении статуса жалобы</b>", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    
    # Получаем данные жалобы для отправки уведомления
    complaint = get_complaint(complaint_id)
    if complaint:
        try:
            # Отправляем уведомление пользователю, который оставил жалобу
            await bot.send_message(
                complaint['user_id'],
                f"✅ <b>Ваша жалоба #{complaint_id} рассмотрена!</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 <b>На кого жаловались:</b> {complaint['reported_user']}\n"
                f"👑 <b>Рассмотрел:</b> {message.from_user.first_name}\n"
                f"📝 <b>Решение:</b> {resolution_text}\n\n"
                f"<i>Спасибо за обращение! Проблема решена.</i>"
            )
            logger.info(f"✅ Уведомление отправлено пользователю {complaint['user_id']} о решении жалобы #{complaint_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление пользователю {complaint['user_id']}: {e}")
    
    await message.answer(
        f"✅ <b>Жалоба #{complaint_id} отмечена как решённая!</b>\n"
        f"Пользователь уведомлён.",
        reply_markup=get_admin_keyboard()
    )
    
    await state.clear()

@dp.callback_query(F.data.startswith("reject_complaint_"))
async def reject_complaint(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        complaint_id = int(callback.data.split("_")[2])
        
        # Обновляем статус жалобы
        success = update_complaint_status(
            complaint_id, 
            'rejected', 
            callback.from_user.id, 
            callback.from_user.first_name,
            "Жалоба отклонена без рассмотрения"
        )
        
        if not success:
            await callback.answer("❌ Ошибка при отклонении жалобы!", show_alert=True)
            return
        
        # Получаем данные жалобы
        complaint = get_complaint(complaint_id)
        if complaint:
            try:
                # Отправляем уведомление пользователю
                await bot.send_message(
                    complaint['user_id'],
                    f"❌ <b>Ваша жалоба #{complaint_id} отклонена</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>На кого жаловались:</b> {complaint['reported_user']}\n"
                    f"👑 <b>Администратор:</b> {callback.from_user.first_name}\n\n"
                    f"<i>Жалоба была отклонена без рассмотрения.</i>"
                )
                logger.info(f"✅ Уведомление об отклонении отправлено пользователю {complaint['user_id']}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление пользователю {complaint['user_id']}: {e}")
        
        await callback.message.edit_text(
            f"❌ <b>Жалоба #{complaint_id} отклонена</b>\n"
            f"Пользователь уведомлён.",
            reply_markup=None
        )
        
        await callback.answer(f"❌ Жалоба #{complaint_id} отклонена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отклонения жалобы: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data == "complaints_back")
async def complaints_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.delete()
    await show_complaints_menu(callback.message)

# ========== ЗАЯВКИ С ТЕМАТИЧЕСКИМИ СООБЩЕНИЯМИ ==========

@dp.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"👤 Пользователь {user_id} начал подачу заявки")
    
    # Проверяем существующую заявку
    existing = get_user_last_application(user_id)
    if existing:
        if existing['status'] == 'pending':
            await message.answer(
                f"⏳ <b>Заявка #{existing['id']} уже на рассмотрении</b>\n"
                f"Система обрабатывает вашу идентификацию...",
                reply_markup=get_user_keyboard()
            )
            return
        elif existing['status'] == 'approved':
            await message.answer(
                f"✅ <b>Идентификация подтверждена</b>\n"
                f"Заявка #{existing['id']} уже одобрена.\n"
                f"Вы не можете подать новую заявку.",
                reply_markup=get_user_keyboard()
            )
            return
    
    await message.answer(
        "<code>> ИНИЦИИРОВАН ПРОТОКОЛ ИДЕНТИФИКАЦИИ...</code>\n\n"
        "✏️ <b>Введите ваш идентификатор в системе (никнейм в игре):</b>\n"
        "(Минимум 2 символа, только буквы и цифры)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ApplicationForm.nickname)

@dp.message(ApplicationForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ПРЕРВАН</code>",
            reply_markup=get_user_keyboard()
        )
        return
    
    nickname = message.text.strip()
    if len(nickname) < 2:
        await message.answer("❌ <b>СИГНАЛ СЛАБЫЙ!</b>\nТребуется минимум 2 символа:\nВведите ваш идентификатор:")
        return
    
    # Проверка на допустимые символы
    if not all(c.isalnum() or c in '_- ' for c in nickname):
        await message.answer("❌ <b>НЕДОПУСТИМЫЕ СИМВОЛЫ!</b>\nИспользуйте только буквы, цифры, дефисы и подчёркивания:\nВведите ваш идентификатор:")
        return
    
    await state.update_data(nickname=nickname)
    await message.answer(
        "<code>> ИДЕНТИФИКАТОР ПРИНЯТ...</code>\n\n"
        "📛 <b>Введите ваше настоящее имя:</b>\n"
        "(Как к вам можно обращаться вне системы)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ApplicationForm.name)

@dp.message(ApplicationForm.name)
async def process_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ПРЕРВАН</code>",
            reply_markup=get_user_keyboard()
        )
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ <b>СИГНАЛ СЛАБЫЙ!</b>\nТребуется минимум 2 символа:\nВведите ваше имя:")
        return
    
    await state.update_data(name=name)
    await message.answer(
        "<code>> ИМЯ ЗАРЕГИСТРИРОВАНО...</code>\n\n"
        "🎂 <b>Введите ваш возраст:</b>\n"
        "(От 14 до 100 лет - требование системы)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ApplicationForm.age)

@dp.message(ApplicationForm.age)
async def process_age(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ПРЕРВАН</code>",
            reply_markup=get_user_keyboard()
        )
        return
    
    try:
        age = int(message.text.strip())
        if age < 14 or age > 100:
            await message.answer("❌ <b>НЕДОПУСТИМЫЙ ВОЗРАСТ!</b>\nТребуется от 14 до 100 лет:\nВведите ваш возраст:")
            return
    except ValueError:
        await message.answer("❌ <b>ОШИБКА СЧИТЫВАНИЯ!</b>\nПожалуйста, введите число:\nВведите ваш возраст:")
        return
    
    await state.update_data(age=age)
    await message.answer(
        "<code>> ВОЗРАСТ ПОДТВЕРЖДЁН...</code>\n\n"
        "🎮 <b>ВЫБЕРИТЕ СВОЮ ФРАКЦИЮ:</b>\n\n"
        "⚙️ <b>Техно-Братство</b>\n"
        "<i>Мастера технологий и инженерии. Строители будущего.</i>\n\n"
        "🔮 <b>Орден Магов</b>\n"
        "<i>Хранители древних знаний и магии. Защитники традиций.</i>\n\n"
        "<code>> ОЖИДАНИЕ ВЫБОРА...</code>",
        reply_markup=get_faction_keyboard()
    )
    await state.set_state(ApplicationForm.faction)

@dp.message(ApplicationForm.faction)
async def process_faction(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ПРЕРВАН</code>",
            reply_markup=get_user_keyboard()
        )
        return
    
    # Определяем выбранную фракцию
    faction_key = None
    for key, name in FACTIONS.items():
        if message.text == name:
            faction_key = key
            break
    
    if not faction_key:
        await message.answer(
            "❌ <b>НЕРАСПОЗНАННЫЙ ВЫБОР!</b>\n"
            "Пожалуйста, выберите фракцию из предложенных вариантов:",
            reply_markup=get_faction_keyboard()
        )
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
            "❌ <b>СИСТЕМНАЯ ОШИБКА!</b>\n"
            "Произошла ошибка при сохранении заявки.\n"
            "Попробуйте ещё раз или обратитесь к администратору.",
            reply_markup=get_user_keyboard()
        )
        await state.clear()
        return
    
    faction_name = FACTIONS.get(faction_key, "Неизвестно")
    faction_desc = "⚙️ Техно-Братство" if faction_key == "techno" else "🔮 Орден Магов"
    
    # Отправляем подтверждение пользователю
    await message.answer(
        f"<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ЗАВЕРШЁН</code>\n\n"
        f"✅ <b>ЗАЯВКА #{app_id} УСПЕШНО ПОДАНА!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Идентификатор:</b> {nickname}\n"
        f"📛 <b>Имя:</b> {name}\n"
        f"🎂 <b>Возраст:</b> {age}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n\n"
        f"⏳ <b>Ожидайте подтверждения от администраторов системы.</b>\n"
        f"Вы будете уведомлены о результате.",
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
        f"🆕 <b>НОВЫЙ СИГНАЛ ИДЕНТИФИКАЦИИ!</b>\n\n"
        f"📝 <b>Заявка #{app_id}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Идентификатор:</b> {nickname}\n"
        f"📛 <b>Имя:</b> {name}\n"
        f"🎂 <b>Возраст:</b> {age}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n"
        f"🆔 <b>ID системы:</b> {user_id}\n"
        f"👤 <b>Username:</b> @{username if username else 'нет'}\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<i>Требуется ваше подтверждение...</i>"
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
            "📭 <b>СИГНАЛ НЕ ОБНАРУЖЕН</b>\n"
            "У вас ещё нет заявок в системе.\n"
            "Нажмите '📝 Подать заявку' для инициализации протокола идентификации.",
            reply_markup=get_user_keyboard()
        )
        return
    
    # Статусы с иконками
    status_info = {
        'pending': ('⏳ <b>НА РАССМОТРЕНИИ</b>', 'Система обрабатывает вашу идентификацию...'),
        'approved': ('✅ <b>ИДЕНТИФИКАЦИЯ ПОДТВЕРЖДЕНА</b>', f'Администратор: {app["admin_name"]}' if app["admin_name"] else ''),
        'rejected': ('❌ <b>ИДЕНТИФИКАЦИЯ ОТКЛОНЕНА</b>', f'Администратор: {app["admin_name"]}' if app["admin_name"] else '')
    }
    
    status_text, status_desc = status_info.get(app['status'], ('❓ <b>НЕИЗВЕСТНЫЙ СТАТУС</b>', ''))
    faction_name = FACTIONS.get(app['faction'], "Неизвестно")
    
    await message.answer(
        f"{status_text}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Заявка #{app['id']}</b>\n"
        f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
        f"📛 <b>Имя:</b> {app['name']}\n"
        f"🎂 <b>Возраст:</b> {app['age']}\n"
        f"🎮 <b>Фракция:</b> {faction_name}\n"
        f"📅 <b>Дата подачи:</b> {app['created_at'][:16]}\n\n"
        f"{status_desc}",
        reply_markup=get_user_keyboard()
    )

# ========== ОСТАЛЬНЫЕ АДМИН-ФУНКЦИИ ==========

@dp.message(F.text == "📋 Новые заявки")
async def show_new_apps(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    pending = get_pending_applications()
    
    if not pending:
        await message.answer(
            "✅ <b>СИГНАЛЫ ОТСУТСТВУЮТ</b>\n"
            "Все заявки рассмотрены!",
            reply_markup=get_admin_keyboard()
        )
        return
    
    await message.answer(
        f"📋 <b>ОЖИДАЮТ РАССМОТРЕНИЯ:</b> {len(pending)}\n"
        f"Отправляю информацию...",
        reply_markup=get_admin_keyboard()
    )
    
    # Отправляем каждую заявку отдельным сообщением
    for app in pending:
        try:
            faction_name = FACTIONS.get(app['faction'], "Неизвестно")
            app_text = (
                f"⏳ <b>Заявка #{app['id']}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
                f"📛 <b>Имя:</b> {app['name']}\n"
                f"🎂 <b>Возраст:</b> {app['age']}\n"
                f"🎮 <b>Фракция:</b> {faction_name}\n"
                f"🆔 <b>ID системы:</b> {app['user_id']}\n"
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
        await message.answer("📭 <b>АРХИВ ПУСТ</b>\nИстория заявок отсутствует.", reply_markup=get_admin_keyboard())
        return
    
    await show_history_page(message, 0)

async def show_history_page(message: Message, offset=0, limit=10):
    applications = get_all_applications(limit, offset)
    total, _, _, _ = get_stats()
    
    if not applications:
        await message.answer("📭 <b>АРХИВ ЗАВЕРШЁН</b>\nБольше нет заявок.", reply_markup=get_admin_keyboard())
        return
    
    # Статусы с иконками
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    response = "📜 <b>АРХИВ ИДЕНТИФИКАЦИЙ</b>\n━━━━━━━━━━━━━━━━\n"
    
    for app in applications:
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        date_str = app['created_at'][:10] if app['created_at'] else '??.??.????'
        response += f"{status_icon}{faction_icon} <b>#{app['id']}</b>: {app['nickname']} ({date_str})\n"
    
    response += f"\n<b>Всего записей:</b> {total}"
    
    await message.answer(
        response,
        reply_markup=get_history_navigation(offset, total, limit, "history_apps")
    )

@dp.message(F.text == "🔍 Поиск заявки")
async def start_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "🔍 <b>ПОИСК В АРХИВЕ</b>\n"
        "Введите идентификатор, имя, username или фракцию для поиска:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SearchForm.query)

@dp.message(SearchForm.query)
async def process_search(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("✅ <b>ПОИСК ОТМЕНЁН</b>", reply_markup=get_admin_keyboard())
        return
    
    search_term = message.text.strip()
    if len(search_term) < 2:
        await message.answer("❌ <b>СЛИШКОМ КОРОТКИЙ ЗАПРОС!</b>\nВведите минимум 2 символа:")
        return
    
    results = search_applications(search_term)
    
    if not results:
        await message.answer(
            f"🔍 <b>ПО ЗАПРОСУ '{search_term}' НИЧЕГО НЕ НАЙДЕНО</b>",
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
    
    response = f"🔍 <b>РЕЗУЛЬТАТЫ ПОИСКА: '{search_term}'</b>\n━━━━━━━━━━━━━━━━\n"
    
    for app in results[:20]:  # Ограничиваем 20 результатами
        status_icon = status_icons.get(app['status'], '❓')
        faction_icon = FACTIONS.get(app['faction'], '🎮').split()[0]
        username = f" @{app['username']}" if app['username'] else ""
        response += f"{status_icon}{faction_icon} <b>#{app['id']}</b>: {app['nickname']} ({app['name']}, {app['age']}){username}\n"
    
    if len(results) > 20:
        response += f"\n... и ещё {len(results) - 20} записей"
    
    await message.answer(response, reply_markup=get_admin_keyboard())
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total, pending, approved, rejected = get_stats()
    complaints_total, complaints_pending, complaints_reviewing, complaints_resolved = get_complaints_stats()
    
    stats_text = (
        f"📊 <b>СТАТИСТИКА СИСТЕМЫ</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 <b>ИДЕНТИФИКАЦИИ:</b>\n"
        f"• Всего: {total}\n"
        f"• ⏳ Ожидают: {pending}\n"
        f"• ✅ Подтверждено: {approved}\n"
        f"• ❌ Отклонено: {rejected}\n\n"
        f"📖 <b>СИГНАЛЫ НЕИСПРАВНОСТЕЙ:</b>\n"
        f"• Всего: {complaints_total}\n"
        f"• ⏳ Ожидают: {complaints_pending}\n"
        f"• 👁️ На анализе: {complaints_reviewing}\n"
        f"• ✅ Устранено: {complaints_resolved}\n\n"
        f"👑 <b>АДМИНИСТРАТОРОВ:</b> {len(ADMIN_IDS)}"
    )
    
    await message.answer(stats_text, reply_markup=get_admin_keyboard())

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
                f"<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ЗАВЕРШЁН</code>\n\n"
                f"✅ <b>ВАША ИДЕНТИФИКАЦИЯ ПОДТВЕРЖДЕНА!</b>\n\n"
                f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
                f"🎮 <b>Фракция:</b> {faction_name}\n"
                f"👑 <b>Администратор системы:</b> {callback.from_user.first_name}\n\n"
                f"<i>Добро пожаловать в систему!</i>"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {app['user_id']}: {e}")
        
        # Обновляем сообщение с заявкой
        faction_name = FACTIONS.get(app['faction'], "Неизвестно")
        await callback.message.edit_text(
            f"✅ <b>Заявка #{app_id} подтверждена</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
            f"📛 <b>Имя:</b> {app['name']}\n"
            f"🎮 <b>Фракция:</b> {faction_name}\n"
            f"👑 <b>Админ системы:</b> {callback.from_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(f"✅ Заявка #{app_id} подтверждена")
        logger.info(f"✅ Админ {user_id} подтвердил заявку #{app_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при подтверждении заявки: {e}")
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
                f"<code>> ПРОТОКОЛ ИДЕНТИФИКАЦИИ ЗАВЕРШЁН</code>\n\n"
                f"❌ <b>ВАША ИДЕНТИФИКАЦИЯ ОТКЛОНЕНА</b>\n\n"
                f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
                f"👑 <b>Администратор системы:</b> {callback.from_user.first_name}\n\n"
                f"<i>Обратитесь к администрации для уточнения деталей.</i>"
            )
        except Exception as e:
            logger.error(f"❌ Не удалось уведомить пользователя {app['user_id']}: {e}")
        
        # Обновляем сообщение с заявкой
        await callback.message.edit_text(
            f"❌ <b>Заявка #{app_id} отклонена</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Идентификатор:</b> {app['nickname']}\n"
            f"👑 <b>Админ системы:</b> {callback.from_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(f"❌ Заявка #{app_id} отклонена")
        logger.info(f"❌ Админ {user_id} отклонил заявку #{app_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отклонении заявки: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("history_apps_"))
async def navigate_history_apps(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        offset = int(callback.data.split("_")[2])
        await show_history_page(callback.message, offset)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка навигации по архиву: {e}")
        await callback.answer("❌ Ошибка навигации!", show_alert=True)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

async def main():
    print("=" * 60)
    print("🤖 СИСТЕМА ИДЕНТИФИКАЦИИ ЗАПУЩЕНА")
    print("=" * 60)
    print(f"🔑 Токен системы: {BOT_TOKEN[:10]}...")
    print(f"👑 Администраторов: {len(ADMIN_IDS)}")
    print(f"🆔 ID админов: {ADMIN_IDS}")
    print(f"🎮 Доступные фракции: {len(FACTIONS)} ({', '.join(FACTIONS.values())})")
    print(f"📅 Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("🚀 Система активирована...")
    print("-" * 60)
    
    # Инициализируем БД
    init_db()
    
    try:
        # Удаляем вебхук (чтобы избежать конфликта)
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Вебхук удалён")
        
        # Запускаем polling
        print("📡 Начинаем сканирование сигналов...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка системы: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Запускаем систему
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Система остановлена пользователем")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка системы: {e}")
