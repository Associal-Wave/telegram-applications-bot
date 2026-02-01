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

def delete_application(app_id):
    """Удаляет заявку из базы данных"""
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM applications WHERE id = ?', (app_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        if deleted:
            print(f"✅ Заявка #{app_id} удалена")
        else:
            print(f"⚠️ Заявка #{app_id} не найдена для удаления")
        return deleted
    except Exception as e:
        print(f"❌ Ошибка удаления заявки #{app_id}: {e}")
        return False

def delete_all_user_applications(user_id):
    """Удаляет ВСЕ заявки пользователя"""
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM applications WHERE user_id = ?', (user_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Удалено {deleted_count} заявок пользователя {user_id}")
        return deleted_count
    except Exception as e:
        print(f"❌ Ошибка удаления заявок пользователя {user_id}: {e}")
        return 0

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

def get_approved_players(limit=100, offset=0):
    """Получает список одобренных игроков"""
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM applications 
        WHERE status = 'approved' 
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
        ''', (limit, offset))
        results = cursor.fetchall()
        conn.close()
        players = []
        for result in results:
            players.append({
                'id': result[0], 'user_id': result[1], 'username': result[2],
                'nickname': result[3], 'name': result[4], 'age': result[5],
                'faction': result[6], 'status': result[7], 'admin_id': result[8],
                'admin_name': result[9], 'created_at': result[10]
            })
        return players
    except Exception as e:
        print(f"❌ Ошибка получения списка игроков: {e}")
        return []

def get_player_count():
    """Получает количество одобренных игроков"""
    try:
        conn = sqlite3.connect('applications.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'approved'")
        count = cursor.fetchone()[0] or 0
        conn.close()
        return count
    except Exception as e:
        print(f"❌ Ошибка получения количества игроков: {e}")
        return 0

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
            [KeyboardButton(text="👥 Список игроков")],
            [KeyboardButton(text="📖 Жалобы")],
            [KeyboardButton(text="🔍 Поиск заявки")],
            [KeyboardButton(text="🗑️ Очистить мои заявки")],
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

def get_confirm_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="✅ Да, удалить"))
    builder.add(KeyboardButton(text="❌ Нет, отмена"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

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

def get_player_actions(player_id):
    """Кнопки для действий с игроком"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_player_{player_id}"))
    builder.add(InlineKeyboardButton(text="📋 Подробнее", callback_data=f"player_info_{player_id}"))
    builder.adjust(2)
    return builder.as_markup()

def get_player_detail_actions(player_id):
    """Кнопки для детального просмотра игрока"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Удалить игрока", callback_data=f"delete_player_{player_id}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="players_back"))
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

def get_players_navigation(offset, total_count, limit=10):
    builder = InlineKeyboardBuilder()
    
    if offset > 0:
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"players_{offset-limit}"))
    
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit
    builder.add(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="players_page"))
    
    if offset + limit < total_count:
        builder.add(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"players_{offset+limit}"))
    
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

class DeleteMyAppsForm(StatesGroup):
    confirm = State()

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
    player_count = get_player_count()
    
    await message.answer(
        f"👑 <b>Админ-панель</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>Ожидают заявок:</b> {len(pending_apps)}\n"
        f"👥 <b>Активных игроков:</b> {player_count}\n"
        f"📖 <b>Жалоб на рассмотрении:</b> {len(pending_complaints)}",
        reply_markup=get_admin_keyboard()
    )

# ========== СПИСОК ИГРОКОВ И УДАЛЕНИЕ ==========

@dp.message(F.text == "👥 Список игроков")
async def show_players_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    player_count = get_player_count()
    
    if player_count == 0:
        await message.answer(
            "👥 <b>Список игроков пуст</b>\n"
            "Нет одобренных заявок.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    await show_players_page(message, 0)

async def show_players_page(message: Message, offset=0, limit=10):
    players = get_approved_players(limit, offset)
    player_count = get_player_count()
    
    if not players:
        await message.answer("👥 <b>Больше нет игроков</b>", reply_markup=get_admin_keyboard())
        return
    
    response = "👥 <b>СПИСОК ИГРОКОВ</b>\n━━━━━━━━━━━━━━━━\n"
    
    for player in players:
        faction_icon = FACTIONS.get(player['faction'], '🎮').split()[0]
        date_str = player['created_at'][:10] if player['created_at'] else '??.??.????'
        username = f" @{player['username']}" if player['username'] else ""
        response += f"{faction_icon} <b>#{player['id']}</b>: {player['nickname']} ({player['age']} л.){username}\n"
    
    response += f"\n<b>Всего игроков:</b> {player_count}"
    
    await message.answer(
        response,
        reply_markup=get_players_navigation(offset, player_count, limit)
    )
    
    # Также отправляем подробную информацию по каждому игроку с кнопками
    for player in players[:3]:  # Показываем первые 3 с кнопками
        try:
            faction_name = FACTIONS.get(player['faction'], "Неизвестно")
            player_info = (
                f"👤 <b>Игрок #{player['id']}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Ник:</b> {player['nickname']}\n"
                f"📛 <b>Имя:</b> {player['name']}\n"
                f"🎂 <b>Возраст:</b> {player['age']}\n"
                f"🎮 <b>Фракция:</b> {faction_name}\n"
                f"🆔 <b>ID:</b> {player['user_id']}\n"
                f"👤 <b>Username:</b> @{player['username'] if player['username'] else 'нет'}\n"
                f"📅 <b>Дата регистрации:</b> {player['created_at'][:16]}\n"
                f"👑 <b>Принял:</b> {player['admin_name'] or 'Неизвестно'}\n"
                f"━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(
                chat_id=message.chat.id,
                text=player_info,
                reply_markup=get_player_actions(player['id'])
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки информации об игроке #{player['id']}: {e}")

@dp.callback_query(F.data.startswith("players_"))
async def navigate_players(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        offset = int(callback.data.split("_")[1])
        await show_players_page(callback.message, offset)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка навигации по списку игроков: {e}")
        await callback.answer("❌ Ошибка навигации!", show_alert=True)

@dp.callback_query(F.data == "players_back")
async def players_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.delete()
    await show_players_list(callback.message)

@dp.callback_query(F.data.startswith("player_info_"))
async def show_player_info(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        player_id = int(callback.data.split("_")[2])
        player = get_application(player_id)
        
        if not player or player['status'] != 'approved':
            await callback.answer("❌ Игрок не найден!", show_alert=True)
            return
        
        faction_name = FACTIONS.get(player['faction'], "Неизвестно")
        player_info = (
            f"👤 <b>ПОДРОБНАЯ ИНФОРМАЦИЯ ОБ ИГРОКЕ</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>ID заявки:</b> #{player['id']}\n"
            f"👤 <b>Ник:</b> {player['nickname']}\n"
            f"📛 <b>Имя:</b> {player['name']}\n"
            f"🎂 <b>Возраст:</b> {player['age']}\n"
            f"🎮 <b>Фракция:</b> {faction_name}\n"
            f"🆔 <b>ID пользователя:</b> {player['user_id']}\n"
            f"👤 <b>Username:</b> @{player['username'] if player['username'] else 'нет'}\n"
            f"📅 <b>Дата регистрации:</b> {player['created_at'][:16]}\n"
            f"👑 <b>Принял админ:</b> {player['admin_name'] or 'Неизвестно'}\n"
            f"🆔 <b>ID админа:</b> {player['admin_id'] or 'Неизвестно'}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<i>Запись создана: {player['created_at']}</i>"
        )
        
        await callback.message.edit_text(
            player_info,
            reply_markup=get_player_detail_actions(player_id)
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка показа информации об игроке: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("delete_player_"))
async def delete_player_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        player_id = int(callback.data.split("_")[2])
        player = get_application(player_id)
        
        if not player:
            await callback.answer("❌ Игрок не найден!", show_alert=True)
            return
        
        # Запрашиваем подтверждение
        confirm_text = (
            f"⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ИГРОКА</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Игрок #{player_id}:</b> {player['nickname']}\n"
            f"📛 <b>Имя:</b> {player['name']}\n"
            f"🎮 <b>Фракция:</b> {FACTIONS.get(player['faction'], 'Неизвестно')}\n\n"
            f"❓ <b>Вы уверены, что хотите удалить этого игрока?</b>\n"
            f"Это действие нельзя отменить!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_player_{player_id}"))
        builder.add(InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_delete_player_{player_id}"))
        builder.adjust(2)
        
        await callback.message.edit_text(
            confirm_text,
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка начала удаления игрока: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("confirm_delete_player_"))
async def confirm_delete_player(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    try:
        player_id = int(callback.data.split("_")[3])
        player = get_application(player_id)
        
        if not player:
            await callback.answer("❌ Игрок не найден!", show_alert=True)
            return
        
        # Удаляем игрока
        deleted = delete_application(player_id)
        
        if deleted:
            # Пытаемся уведомить игрока (если бот ещё может ему писать)
            try:
                await bot.send_message(
                    player['user_id'],
                    f"❌ <b>ВАША РЕГИСТРАЦИЯ АННУЛИРОВАНА</b>\n\n"
                    f"👤 <b>Игрок:</b> {player['nickname']}\n"
                    f"👑 <b>Администратор:</b> {callback.from_user.first_name}\n\n"
                    f"<i>Ваша учётная запись была удалена из системы.</i>"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить игрока {player['user_id']}: {e}")
            
            await callback.message.edit_text(
                f"🗑️ <b>Игрок #{player_id} удалён</b>\n"
                f"Ник: {player['nickname']}",
                reply_markup=None
            )
            
            await callback.answer("✅ Игрок удалён")
            logger.info(f"🗑️ Админ {callback.from_user.id} удалил игрока #{player_id}")
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка при удалении игрока #{player_id}</b>",
                reply_markup=None
            )
            await callback.answer("❌ Ошибка удаления", show_alert=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка удаления игрока: {e}")
        await callback.answer("❌ Произошла ошибка!", show_alert=True)

@dp.callback_query(F.data.startswith("cancel_delete_player_"))
async def cancel_delete_player(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.delete()
    await callback.answer("❌ Удаление отменено")

# ========== ОЧИСТКА СВОИХ ЗАЯВОК (ДЛЯ АДМИНОВ) ==========

@dp.message(F.text == "🗑️ Очистить мои заявки")
async def clear_my_applications(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    # Получаем все заявки текущего админа
    user_id = message.from_user.id
    all_apps = get_all_applications(limit=1000)  # Большой лимит
    my_apps = [app for app in all_apps if app['user_id'] == user_id]
    
    if not my_apps:
        await message.answer(
            "🗑️ <b>У вас нет заявок</b>\n"
            "Нечего удалять.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # Считаем по статусам
    pending_count = len([app for app in my_apps if app['status'] == 'pending'])
    approved_count = len([app for app in my_apps if app['status'] == 'approved'])
    rejected_count = len([app for app in my_apps if app['status'] == 'rejected'])
    total_count = len(my_apps)
    
    confirm_text = (
        f"⚠️ <b>ОЧИСТКА ВАШИХ ЗАЯВОК</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Ваша статистика:</b>\n"
        f"• 📋 Всего заявок: {total_count}\n"
        f"• ⏳ Ожидают: {pending_count}\n"
        f"• ✅ Приняты: {approved_count}\n"
        f"• ❌ Отклонены: {rejected_count}\n\n"
        f"❓ <b>Вы уверены, что хотите удалить ВСЕ свои заявки?</b>\n"
        f"Это действие нельзя отменить!\n\n"
        f"<i>Напишите '✅ Да, удалить' для подтверждения</i>"
    )
    
    await message.answer(
        confirm_text,
        reply_markup=get_confirm_keyboard()
    )
    
    await state.set_state(DeleteMyAppsForm.confirm)
    await state.update_data(my_apps_count=total_count)

@dp.message(DeleteMyAppsForm.confirm)
async def process_clear_confirm(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text == "❌ Нет, отмена":
        await state.clear()
        await message.answer(
            "✅ <b>Очистка отменена</b>",
            reply_markup=get_admin_keyboard()
        )
        return
    
    if message.text != "✅ Да, удалить":
        await message.answer(
            "❌ <b>Неподтверждение</b>\n"
            "Напишите '✅ Да, удалить' для подтверждения или '❌ Нет, отмена' для отмены.",
            reply_markup=get_confirm_keyboard()
        )
        return
    
    # Удаляем все заявки пользователя
    deleted_count = delete_all_user_applications(user_id)
    
    await message.answer(
        f"🗑️ <b>Очистка завершена</b>\n"
        f"Удалено {deleted_count} ваших заявок.",
        reply_markup=get_admin_keyboard()
    )
    
    await state.clear()

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

# (Весь код для заявок, истории, поиска, статистики и обработки заявок остаётся таким же,
# только добавлены новые пункты в админ-меню)

# ... [Здесь весь остальной код для заявок, такой же как в предыдущем варианте] ...

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
