# admin_handlers.py — ПОЛНАЯ РАБОЧАЯ МЕГА-АДМИНКА С РАСШИРЕНИЯМИ
import asyncio
import json
import os
import random
import logging
import csv
import io
import sys
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import *
from states import AdminStates
from promo import PromoCodeManager
from models import (
    ExclusiveCard, ShopItem, Lootbox, WheelPrize, GameStats,
    Quest, UserQuest, Achievement, ABTest, Poll, MiniGame
)

admin_router = Router()
router = admin_router

logger = logging.getLogger(__name__)

# ─── Глобальные переменные ──────────────────────────────────────────────────────
bot = None
users = None
cards = None
card_pool = None
trades = None
shop_items = None
orders = None
exclusive_cards = None
promo_manager = None
current_wheel = None
lootboxes = None
save_data = None
load_data = None
get_or_create_user = None
get_user_by_username = None
update_user_interaction = None
add_premium = None
add_reduced_cd = None
add_reduced_trade_cd = None
add_cooldown = None
update_card_pool = None
get_rarity_color = None
get_rarity_name = None
is_video_card = None
get_image_path = None
get_video_path = None
ban_user = None
confirm_order = None
reject_order = None
send_order_notification = None
get_top_spenders = None
DATA_DIR = None
IMAGES_DIR = None
VIDEOS_DIR = None
USERS_FILE = None
Card = None

# ─── Лог и расширенные данные ───────────────────────────────────────────────────
ADMIN_LOG_FILE = None
BAD_WORDS_FILE = None
TEMPLATES_FILE = None
SHOP_FILE = None
EXCLUSIVE_FILE = None
LOOTBOXES_FILE = None
WHEEL_FILE = None
SETTINGS_FILE = None
SCHEDULER_FILE = None
EVENTS_FILE = None
QUESTS_FILE = None
ACHIEVEMENTS_FILE = None
AB_TESTS_FILE = None
CUSTOM_TEXTS_FILE = None
POLLS_FILE = None
MINIGAMES_FILE = None
SNAPSHOTS_DIR = None

admin_action_log: List[Dict] = []
bad_words: List[str] = []
templates: Dict[str, str] = {}
bot_settings: Dict = {}
scheduled_tasks: List[Dict] = []
events_config: Dict = {}
quests: Dict[str, Quest] = {}
user_quests: Dict[int, Dict[str, UserQuest]] = {}
achievements: Dict[str, Achievement] = {}
user_achievements: Dict[int, List[str]] = {}
ab_tests: Dict[str, ABTest] = {}
custom_texts: Dict[str, str] = {}
polls: Dict[str, Poll] = {}
minigames: Dict[str, MiniGame] = {}

# Кэш для весов
_cached_weights = {"basic": 9790, "cool": 1000, "legendary": 150, "vinyl figure": 60}


def setup_admin_handlers(bot_i, users_d, cards_d, card_pool_r, trades_d,
                         shop_d, orders_d, excl_d, promo_m, wheel_r,
                         save_fn, load_fn, get_user_fn, by_username_fn,
                         update_user_fn,
                         add_premium_fn, add_red_cd_fn, add_red_tcd_fn,
                         add_cd_fn, upd_pool_fn,
                         rarity_color_fn, rarity_name_fn,
                         is_video_fn, img_path_fn, vid_path_fn,
                         ban_fn, confirm_order_fn, reject_order_fn,
                         order_notif_fn, top_spenders_fn,
                         data_dir, images_dir, videos_dir,
                         users_file, card_class,
                         lootboxes_d=None, lootboxes_fn=None):
    global bot, users, cards, card_pool, trades, shop_items, orders, exclusive_cards
    global promo_manager, current_wheel, save_data, load_data
    global get_or_create_user, get_user_by_username, update_user_interaction
    global add_premium, add_reduced_cd, add_reduced_trade_cd, add_cooldown, update_card_pool
    global get_rarity_color, get_rarity_name, is_video_card, get_image_path, get_video_path
    global ban_user, confirm_order, reject_order, send_order_notification, get_top_spenders
    global DATA_DIR, IMAGES_DIR, VIDEOS_DIR, USERS_FILE, Card
    global ADMIN_LOG_FILE, BAD_WORDS_FILE, TEMPLATES_FILE, SHOP_FILE, EXCLUSIVE_FILE
    global LOOTBOXES_FILE, WHEEL_FILE, SETTINGS_FILE
    global SCHEDULER_FILE, EVENTS_FILE, QUESTS_FILE, ACHIEVEMENTS_FILE
    global AB_TESTS_FILE, CUSTOM_TEXTS_FILE, POLLS_FILE, MINIGAMES_FILE, SNAPSHOTS_DIR
    global admin_action_log, bad_words, templates, bot_settings, lootboxes
    global scheduled_tasks, events_config, quests, user_quests
    global achievements, user_achievements, ab_tests, custom_texts, polls, minigames
    
    bot = bot_i; users = users_d; cards = cards_d; card_pool = card_pool_r
    trades = trades_d; shop_items = shop_d; orders = orders_d; exclusive_cards = excl_d
    promo_manager = promo_m; current_wheel = wheel_r
    save_data = save_fn; load_data = load_fn
    get_or_create_user = get_user_fn; get_user_by_username = by_username_fn
    update_user_interaction = update_user_fn
    add_premium = add_premium_fn; add_reduced_cd = add_red_cd_fn
    add_reduced_trade_cd = add_red_tcd_fn; add_cooldown = add_cd_fn
    update_card_pool = upd_pool_fn
    get_rarity_color = rarity_color_fn; get_rarity_name = rarity_name_fn
    is_video_card = is_video_fn; get_image_path = img_path_fn; get_video_path = vid_path_fn
    ban_user = ban_fn; confirm_order = confirm_order_fn; reject_order = reject_order_fn
    send_order_notification = order_notif_fn; get_top_spenders = top_spenders_fn
    DATA_DIR = data_dir; IMAGES_DIR = images_dir; VIDEOS_DIR = videos_dir
    USERS_FILE = users_file; Card = card_class
    
    if lootboxes_d is not None:
        lootboxes = lootboxes_d
    
    # Инициализация путей
    ADMIN_LOG_FILE = DATA_DIR / "admin_log.json"
    BAD_WORDS_FILE = DATA_DIR / "bad_words.json"
    TEMPLATES_FILE = DATA_DIR / "templates.json"
    SHOP_FILE = DATA_DIR / "shop.json"
    EXCLUSIVE_FILE = DATA_DIR / "exclusive.json"
    LOOTBOXES_FILE = DATA_DIR / "lootboxes.json"
    WHEEL_FILE = DATA_DIR / "wheel.json"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    SCHEDULER_FILE = DATA_DIR / "scheduler.json"
    EVENTS_FILE = DATA_DIR / "events.json"
    QUESTS_FILE = DATA_DIR / "quests.json"
    ACHIEVEMENTS_FILE = DATA_DIR / "achievements.json"
    AB_TESTS_FILE = DATA_DIR / "ab_tests.json"
    CUSTOM_TEXTS_FILE = DATA_DIR / "custom_texts.json"
    POLLS_FILE = DATA_DIR / "polls.json"
    MINIGAMES_FILE = DATA_DIR / "minigames.json"
    SNAPSHOTS_DIR = DATA_DIR / "snapshots"
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    
    load_admin_data()
    load_bot_settings()
    load_extended_data()


def load_extended_data():
    """Загрузка расширенных данных"""
    global scheduled_tasks, events_config, quests, user_quests
    global achievements, user_achievements, ab_tests, custom_texts, polls, minigames
    
    try:
        if SCHEDULER_FILE and SCHEDULER_FILE.exists():
            with open(SCHEDULER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                scheduled_tasks = data.get("tasks", [])
        
        if EVENTS_FILE and EVENTS_FILE.exists():
            with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                events_config = json.load(f)
        else:
            events_config = {"happy_hours": [], "weekend_madness": {"enabled": False, "discount": 15}}
        
        if QUESTS_FILE and QUESTS_FILE.exists():
            with open(QUESTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                quests = {k: Quest.from_dict(v) for k, v in data.get("quests", {}).items()}
                user_quests = {
                    int(k): {qid: UserQuest.from_dict(qd) for qid, qd in v.items()}
                    for k, v in data.get("user_quests", {}).items()
                }
        
        if ACHIEVEMENTS_FILE and ACHIEVEMENTS_FILE.exists():
            with open(ACHIEVEMENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                achievements = {k: Achievement.from_dict(v) for k, v in data.get("achievements", {}).items()}
                user_achievements = {int(k): v for k, v in data.get("user_achievements", {}).items()}
        
        if AB_TESTS_FILE and AB_TESTS_FILE.exists():
            with open(AB_TESTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                ab_tests = {k: ABTest.from_dict(v) for k, v in data.items()}
        
        if CUSTOM_TEXTS_FILE and CUSTOM_TEXTS_FILE.exists():
            with open(CUSTOM_TEXTS_FILE, 'r', encoding='utf-8') as f:
                custom_texts = json.load(f)
        else:
            custom_texts = {
                "welcome": "Добро пожаловать, {username}! 🎉\n\nИспользуй /drop чтобы получить карточку!",
                "drop_cooldown": "⏳ Кулдаун! Жди ещё {time}",
                "drop_success": "🎴 Вы получили: {card_name} ({rarity})!"
            }
        
        if POLLS_FILE and POLLS_FILE.exists():
            with open(POLLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                polls = {k: Poll.from_dict(v) for k, v in data.items()}
        
        if MINIGAMES_FILE and MINIGAMES_FILE.exists():
            with open(MINIGAMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                minigames = {k: MiniGame.from_dict(v) for k, v in data.items()}
        else:
            # Создать дефолтные мини-игры
            minigames = {
                "roulette": MiniGame(
                    game_id="roulette", name="🎡 Рулетка", game_type="roulette",
                    min_bet=10, max_bet=500, win_chance=45.0, multiplier=2.0
                ),
                "rps": MiniGame(
                    game_id="rps", name="✂️ Камень-ножницы-бумага", game_type="rps",
                    min_bet=10, max_bet=200, win_chance=50.0, multiplier=1.9
                ),
                "dice": MiniGame(
                    game_id="dice", name="🎲 Кости", game_type="dice",
                    min_bet=10, max_bet=300, win_chance=49.5, multiplier=1.98
                )
            }
    except Exception as e:
        logger.error(f"Ошибка загрузки расширенных данных: {e}")


def save_extended_data():
    """Сохранение расширенных данных"""
    try:
        if SCHEDULER_FILE:
            with open(SCHEDULER_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tasks": scheduled_tasks}, f, ensure_ascii=False, indent=2)
        
        if EVENTS_FILE:
            with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(events_config, f, ensure_ascii=False, indent=2)
        
        if QUESTS_FILE:
            with open(QUESTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "quests": {k: v.to_dict() for k, v in quests.items()},
                    "user_quests": {
                        str(k): {qid: qd.to_dict() for qid, qd in v.items()}
                        for k, v in user_quests.items()
                    }
                }, f, ensure_ascii=False, indent=2)
        
        if ACHIEVEMENTS_FILE:
            with open(ACHIEVEMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "achievements": {k: v.to_dict() for k, v in achievements.items()},
                    "user_achievements": {str(k): v for k, v in user_achievements.items()}
                }, f, ensure_ascii=False, indent=2)
        
        if AB_TESTS_FILE:
            with open(AB_TESTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in ab_tests.items()}, f, ensure_ascii=False, indent=2)
        
        if CUSTOM_TEXTS_FILE:
            with open(CUSTOM_TEXTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(custom_texts, f, ensure_ascii=False, indent=2)
        
        if POLLS_FILE:
            with open(POLLS_FILE, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in polls.items()}, f, ensure_ascii=False, indent=2)
        
        if MINIGAMES_FILE:
            with open(MINIGAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in minigames.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения расширенных данных: {e}")


def log_admin_action(admin_id: int, action: str, target: str = None, details: str = None):
    """Логирование действий администратора"""
    global admin_action_log
    admin = users.get(admin_id) if users else None
    admin_name = f"@{admin.username}" if admin else str(admin_id)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "admin_id": admin_id,
        "admin_name": admin_name,
        "action": action,
        "target": target,
        "details": details
    }
    admin_action_log.append(entry)
    
    if len(admin_action_log) > 1000:
        admin_action_log = admin_action_log[-1000:]
    
    save_admin_data()


def save_admin_data():
    """Сохранение админ-данных"""
    global admin_action_log, bad_words, templates
    if not DATA_DIR:
        return
    try:
        with open(ADMIN_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(admin_action_log, f, ensure_ascii=False, indent=2)
        with open(BAD_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bad_words, f, ensure_ascii=False, indent=2)
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения админ-данных: {e}")


def load_admin_data():
    """Загрузка админ-данных"""
    global admin_action_log, bad_words, templates
    if not DATA_DIR:
        return
    try:
        if ADMIN_LOG_FILE.exists():
            with open(ADMIN_LOG_FILE, 'r', encoding='utf-8') as f:
                admin_action_log = json.load(f)
        else:
            admin_action_log = []
        
        if BAD_WORDS_FILE.exists():
            with open(BAD_WORDS_FILE, 'r', encoding='utf-8') as f:
                bad_words = json.load(f)
        else:
            bad_words = []
        
        if TEMPLATES_FILE.exists():
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                templates = json.load(f)
        else:
            templates = {}
    except Exception as e:
        logger.error(f"Ошибка загрузки админ-данных: {e}")
        admin_action_log = []
        bad_words = []
        templates = {}


def load_bot_settings():
    """Загрузка настроек бота"""
    global bot_settings
    if not DATA_DIR:
        bot_settings = {}
        return
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                bot_settings = json.load(f)
        else:
            bot_settings = {
                "maintenance_mode": False,
                "registration_enabled": True,
                "trades_enabled": True,
                "drops_enabled": True,
                "wheel_enabled": True,
                "level_system_enabled": True,
                "flash_sale_active": False,
                "flash_sale_percent": 20,
                "secret_shop_active": False,
                "secret_shop_password": None
            }
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")
        bot_settings = {}


def _order_card_name(order):
    global cards
    if order.card_id == "skip_card_cooldown": 
        return "⚡ Скип кулдауна карточки"
    if order.card_id == "skip_trade_cooldown": 
        return "🔄 Скип кулдауна обменов"
    if order.card_id == "buy_level_1": 
        return "🎮 +1 уровень"
    if order.card_id == "buy_level_5": 
        return "🎮 +5 уровней"
    if order.card_id.startswith("lootbox_"):
        return "📦 Лутбокс"
    card = cards.get(order.card_id) if cards else None
    return card.name if card else "Неизвестный товар"

# ════════════════════════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ АДМИНА
# ════════════════════════════════════════════════════════════════════════════════
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ <b>Нет доступа.</b>")
        return
    
    log_admin_action(message.from_user.id, "open_admin_panel")
    
    keyboard = InlineKeyboardBuilder()
    
    # Управление пользователями
    keyboard.add(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users_menu"))
    keyboard.add(InlineKeyboardButton(text="🎁 Массовая выдача", callback_data="admin_mass_give_menu"))
    keyboard.add(InlineKeyboardButton(text="⛔ Бан / Разбан", callback_data="admin_ban_user"))
    keyboard.add(InlineKeyboardButton(text="❄️ Заморозка", callback_data="admin_freeze_user"))
    
    # Карточки
    keyboard.add(InlineKeyboardButton(text="➕ Добавить карточку", callback_data="admin_add_card"))
    keyboard.add(InlineKeyboardButton(text="🎬 Добавить видео", callback_data="admin_add_video_card"))
    keyboard.add(InlineKeyboardButton(text="🗑️ Удалить карточку", callback_data="admin_delete_card"))
    keyboard.add(InlineKeyboardButton(text="📋 Список карточек", callback_data="admin_list_cards"))
    keyboard.add(InlineKeyboardButton(text="⚖️ Балансировка шансов", callback_data="admin_balance_weights"))
    
    # Магазин и монетизация
    keyboard.add(InlineKeyboardButton(text="🛒 Магазин", callback_data="admin_shop_menu"))
    keyboard.add(InlineKeyboardButton(text="🎪 Эксклюзивы", callback_data="admin_exclusive_menu"))
    keyboard.add(InlineKeyboardButton(text="📦 Лутбоксы", callback_data="admin_lootboxes_menu"))
    keyboard.add(InlineKeyboardButton(text="🎡 Колесо фортуны", callback_data="admin_wheel_menu"))
    keyboard.add(InlineKeyboardButton(text="🎫 Промокоды", callback_data="admin_create_promo"))
    
    # Игры и квесты
    keyboard.add(InlineKeyboardButton(text="📜 Квесты", callback_data="admin_quests_menu"))
    keyboard.add(InlineKeyboardButton(text="🏆 Достижения", callback_data="admin_achievements_menu"))
    keyboard.add(InlineKeyboardButton(text="🎲 Мини-игры", callback_data="admin_minigames_menu"))
    
    # Аналитика и тесты
    keyboard.add(InlineKeyboardButton(text="📈 Анализ экономики", callback_data="admin_economy"))
    keyboard.add(InlineKeyboardButton(text="🧪 A/B тесты", callback_data="admin_ab_tests_menu"))
    keyboard.add(InlineKeyboardButton(text="📋 Опросы", callback_data="admin_polls_menu"))
    
    # Автоматизация
    keyboard.add(InlineKeyboardButton(text="⏰ Планировщик", callback_data="admin_scheduler"))
    keyboard.add(InlineKeyboardButton(text="🎉 Ивенты", callback_data="admin_events_menu"))
    
    # Модерация
    keyboard.add(InlineKeyboardButton(text="🚫 Чёрный список", callback_data="admin_bad_words_menu"))
    keyboard.add(InlineKeyboardButton(text="📝 Шаблоны", callback_data="admin_templates_menu"))
    
    # Система
    keyboard.add(InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="admin_settings"))
    keyboard.add(InlineKeyboardButton(text="✏️ Тексты бота", callback_data="admin_custom_texts"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="📈 Графики", callback_data="admin_activity_charts"))
    keyboard.add(InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance"))
    keyboard.add(InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders"))
    keyboard.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    keyboard.add(InlineKeyboardButton(text="📋 Лог действий", callback_data="admin_action_log_view"))
    keyboard.add(InlineKeyboardButton(text="💾 Бекап", callback_data="admin_snapshot_menu"))
    keyboard.add(InlineKeyboardButton(text="🔄 Перезапуск", callback_data="admin_restart"))
    
    keyboard.adjust(2)
    
    await message.answer(
        "⚙️ <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"🎴 Карточек: {len(cards)}\n"
        f"📦 Заказов: {len(orders)}\n\n"
        "Выберите действие:",
        reply_markup=keyboard.as_markup()
    )


# ════════════════════════════════════════════════════════════════════════════════
# 1.4 АНАЛИЗ ЭКОНОМИКИ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_economy")
async def admin_economy_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    total_tokens = sum(u.tokens for u in users.values())
    avg_balance = total_tokens // len(users) if users else 0
    
    card_sales = sum(o.price for o in orders.values() if o.status == "confirmed" and o.card_id in cards)
    lootbox_sales = sum(o.price for o in orders.values() if o.status == "confirmed" and "lootbox" in o.card_id)
    premium_sales = sum(o.price for o in orders.values() if o.status == "confirmed" and "premium" in str(o.card_id))
    other_sales = sum(o.price for o in orders.values() if o.status == "confirmed") - card_sales - lootbox_sales - premium_sales
    
    total_sales = card_sales + lootbox_sales + premium_sales + other_sales
    
    # Топ-карты по продажам
    card_sales_count = defaultdict(int)
    for o in orders.values():
        if o.status == "confirmed" and o.card_id in cards:
            card_sales_count[o.card_id] += 1
    
    top_cards = sorted(card_sales_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_economy"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    text = (
        f"📈 <b>Анализ экономики</b>\n\n"
        f"🎫 Токенов в обращении: {total_tokens:,}\n"
        f"👤 Средний баланс: {avg_balance}🎫\n\n"
        f"💰 <b>Структура продаж:</b>\n"
        f"🎴 Карточки: {card_sales:,}₽ ({card_sales/total_sales*100 if total_sales else 0:.1f}%)\n"
        f"📦 Лутбоксы: {lootbox_sales:,}₽ ({lootbox_sales/total_sales*100 if total_sales else 0:.1f}%)\n"
        f"💎 Премиум: {premium_sales:,}₽ ({premium_sales/total_sales*100 if total_sales else 0:.1f}%)\n"
        f"🔧 Прочее: {other_sales:,}₽ ({other_sales/total_sales*100 if total_sales else 0:.1f}%)\n"
        f"💵 <b>Всего продаж:</b> {total_sales:,}₽\n\n"
        f"🏆 <b>Топ-5 карт по продажам:</b>\n"
    )
    
    for card_id, count in top_cards:
        card = cards.get(card_id)
        name = card.name if card else card_id
        text += f"• {name}: {count} шт.\n"
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# 2.1 ПЛАНИРОВЩИК ЗАДАЧ (SCHEDULER)
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_scheduler")
async def admin_scheduler_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🎫 Запланировать токены", callback_data="admin_schedule_tokens"))
    kb.add(InlineKeyboardButton(text="🎴 Запланировать карту", callback_data="admin_schedule_card"))
    kb.add(InlineKeyboardButton(text="📋 Список задач", callback_data="admin_schedule_list"))
    kb.add(InlineKeyboardButton(text="🗑️ Удалить задачу", callback_data="admin_schedule_delete"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    pending = [t for t in scheduled_tasks if t.get("status") == "pending"]
    
    await callback.message.edit_text(
        f"⏰ <b>Планировщик задач</b>\n\n"
        f"📋 Активных: {len(pending)}\n"
        f"✅ Выполнено: {len(scheduled_tasks) - len(pending)}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_schedule_tokens")
async def admin_schedule_tokens(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎫 <b>Запланировать выдачу токенов</b>\n\n"
        "Введите данные в формате:\n"
        "<code>ДД.ММ.ГГГГ ЧЧ:ММ | количество | @username</code>\n\n"
        "Пример для всех: <code>25.12.2026 23:59 | 100 | all</code>\n"
        "Пример для юзера: <code>25.12.2026 23:59 | 100 | @username</code>"
    )
    await state.set_state(AdminStates.waiting_for_scheduled_task)
    await state.update_data(schedule_type="tokens")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_schedule_card")
async def admin_schedule_card(callback: types.CallbackQuery, state: FSMContext):
    cards_list = "\n".join([f"<code>{cid}</code>: {c.name}" for cid, c in list(cards.items())[:15]])
    await callback.message.answer(
        f"🎴 <b>Запланировать выдачу карты</b>\n\n"
        f"Доступные карты:\n{cards_list}\n\n"
        f"Введите данные в формате:\n"
        f"<code>ДД.ММ.ГГГГ ЧЧ:ММ | card_id | @username</code>\n\n"
        f"Пример: <code>25.12.2026 23:59 | card_123 | all</code>"
    )
    await state.set_state(AdminStates.waiting_for_scheduled_task)
    await state.update_data(schedule_type="card")
    await callback.answer()


@router.message(AdminStates.waiting_for_scheduled_task)
async def process_scheduled_task(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    data = await state.get_data()
    schedule_type = data.get("schedule_type")
    
    try:
        parts = message.text.strip().split("|")
        if len(parts) < 3:
            raise ValueError("Неверный формат")
        
        datetime_str = parts[0].strip()
        value = parts[1].strip()
        target = parts[2].strip().lstrip('@')
        
        exec_time = datetime.strptime(datetime_str, "%d.%m.%Y %H:%M")
        
        if exec_time < datetime.now():
            await message.answer("❌ Нельзя запланировать на прошедшее время!")
            await state.clear()
            return
        
        task = {
            "id": f"task_{int(datetime.now().timestamp())}",
            "type": schedule_type,
            "value": value,
            "target": target,
            "exec_time": exec_time.isoformat(),
            "status": "pending",
            "created_by": message.from_user.id,
            "created_at": datetime.now().isoformat()
        }
        
        scheduled_tasks.append(task)
        save_extended_data()
        log_admin_action(message.from_user.id, "schedule_task", task["id"], f"{schedule_type}: {value} to {target}")
        
        await message.answer(
            f"✅ <b>Задача запланирована!</b>\n\n"
            f"🆔 {task['id']}\n"
            f"⏰ {exec_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🎁 {schedule_type}: {value}\n"
            f"👤 Для: {target}"
        )
    except ValueError as e:
        await message.answer(f"❌ Ошибка формата! Используйте:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ | значение | @username</code>")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_schedule_list")
async def admin_schedule_list(callback: types.CallbackQuery):
    pending = [t for t in scheduled_tasks if t.get("status") == "pending"]
    
    if not pending:
        await callback.answer("Нет активных задач", show_alert=True)
        return
    
    text = "⏰ <b>Запланированные задачи</b>\n\n"
    for task in pending[:10]:
        exec_time = datetime.fromisoformat(task["exec_time"]).strftime("%d.%m %H:%M")
        text += f"🆔 {task['id']}\n"
        text += f"⏰ {exec_time} | {task['type']}: {task['value']}\n"
        text += f"👤 {task['target']}\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_scheduler"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_schedule_delete")
async def admin_schedule_delete(callback: types.CallbackQuery, state: FSMContext):
    pending = [t for t in scheduled_tasks if t.get("status") == "pending"]
    
    if not pending:
        await callback.answer("Нет активных задач", show_alert=True)
        return
    
    text = "Введите ID задачи для удаления:\n\n"
    for task in pending[:10]:
        text += f"• <code>{task['id']}</code> — {task['type']}: {task['value']}\n"
    
    await callback.message.answer(text)
    await state.set_state(AdminStates.waiting_for_schedule_delete)
    await callback.answer()


@router.message(AdminStates.waiting_for_schedule_delete)
async def process_schedule_delete(message: types.Message, state: FSMContext):
    task_id = message.text.strip()
    
    for task in scheduled_tasks:
        if task.get("id") == task_id and task.get("status") == "pending":
            task["status"] = "cancelled"
            save_extended_data()
            log_admin_action(message.from_user.id, "cancel_task", task_id)
            await message.answer(f"✅ Задача {task_id} отменена!")
            await state.clear()
            return
    
    await message.answer(f"❌ Задача {task_id} не найдена!")
    await state.clear()


# ════════════════════════════════════════════════════════════════════════════════
# 2.3 ИВЕНТЫ (HAPPY HOURS, WEEKEND MADNESS)
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_events_menu")
async def admin_events_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    hh_count = len(events_config.get("happy_hours", []))
    weekend = events_config.get("weekend_madness", {"enabled": False, "discount": 15})
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🎉 Добавить счастливый час", callback_data="admin_add_happy_hour"))
    kb.add(InlineKeyboardButton(text="📋 Список счастливых часов", callback_data="admin_list_happy_hours"))
    kb.add(InlineKeyboardButton(text="🗑️ Удалить счастливый час", callback_data="admin_delete_happy_hour"))
    kb.add(InlineKeyboardButton(
        text=f"🔥 Выходные безумия: {'✅' if weekend.get('enabled') else '❌'}",
        callback_data="admin_toggle_weekend"
    ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"🎉 <b>Управление ивентами</b>\n\n"
        f"🎁 Счастливых часов: {hh_count}\n"
        f"🔥 Выходные безумия: {'ВКЛ' if weekend.get('enabled') else 'ВЫКЛ'} (скидка {weekend.get('discount', 15)}%)\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_add_happy_hour")
async def admin_add_happy_hour(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎉 <b>Добавить счастливый час</b>\n\n"
        "Введите время в формате:\n"
        "<code>ЧЧ:ММ-ЧЧ:ММ | множитель | дни</code>\n\n"
        "Пример: <code>20:00-22:00 | 2 | пн,ср,пт</code>\n"
        "Множитель: 2 = x2 дроп, 1.5 = +50% опыта\n"
        "Дни: пн,вт,ср,чт,пт,сб,вс или all"
    )
    await state.set_state(AdminStates.waiting_for_happy_hour_time)
    await callback.answer()


@router.message(AdminStates.waiting_for_happy_hour_time)
async def process_happy_hour(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split("|")
        time_range = parts[0].strip()
        multiplier = float(parts[1].strip())
        days_str = parts[2].strip()
        
        start_time, end_time = time_range.split("-")
        
        days = days_str.split(",") if days_str != "all" else ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        
        happy_hour = {
            "id": f"hh_{int(datetime.now().timestamp())}",
            "start": start_time.strip(),
            "end": end_time.strip(),
            "multiplier": multiplier,
            "days": days,
            "enabled": True
        }
        
        if "happy_hours" not in events_config:
            events_config["happy_hours"] = []
        events_config["happy_hours"].append(happy_hour)
        save_extended_data()
        log_admin_action(message.from_user.id, "add_happy_hour", happy_hour["id"])
        
        await message.answer(
            f"✅ <b>Счастливый час добавлен!</b>\n\n"
            f"⏰ {start_time}-{end_time}\n"
            f"📊 Множитель: x{multiplier}\n"
            f"📅 Дни: {', '.join(days)}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка формата: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_list_happy_hours")
async def admin_list_happy_hours(callback: types.CallbackQuery):
    happy_hours = events_config.get("happy_hours", [])
    
    if not happy_hours:
        await callback.answer("Нет счастливых часов", show_alert=True)
        return
    
    text = "🎉 <b>Счастливые часы</b>\n\n"
    for hh in happy_hours[:15]:
        status = "✅" if hh.get("enabled", True) else "❌"
        text += f"{status} {hh['start']}-{hh['end']} | x{hh['multiplier']} | {', '.join(hh['days'])}\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_events_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_toggle_weekend")
async def admin_toggle_weekend(callback: types.CallbackQuery, state: FSMContext):
    weekend = events_config.get("weekend_madness", {"enabled": False, "discount": 15})
    
    if not weekend.get("enabled"):
        # Включаем — запрашиваем скидку
        await callback.message.answer(
            "🔥 <b>Выходные безумия</b>\n\n"
            "Введите процент скидки (5-30):"
        )
        await state.set_state(AdminStates.waiting_for_weekend_discount)
        await callback.answer()
    else:
        # Выключаем
        weekend["enabled"] = False
        events_config["weekend_madness"] = weekend
        save_extended_data()
        log_admin_action(callback.from_user.id, "toggle_weekend", None, "disabled")
        await callback.answer("🔥 Выходные безумия выключены!", show_alert=True)
        await admin_events_menu(callback)


@router.message(AdminStates.waiting_for_weekend_discount)
async def process_weekend_discount(message: types.Message, state: FSMContext):
    try:
        discount = int(message.text.strip())
        if discount < 5 or discount > 30:
            raise ValueError
        
        weekend = events_config.get("weekend_madness", {"enabled": False, "discount": 15})
        weekend["enabled"] = True
        weekend["discount"] = discount
        events_config["weekend_madness"] = weekend
        save_extended_data()
        log_admin_action(message.from_user.id, "toggle_weekend", None, f"enabled, {discount}%")
        
        await message.answer(f"✅ Выходные безумия включены! Скидка {discount}%")
    except:
        await message.answer("❌ Введите число от 5 до 30!")
        return
    
    await state.clear()


# ════════════════════════════════════════════════════════════════════════════════
# 4.1 КВЕСТЫ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_quests_menu")
async def admin_quests_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📜 Создать квест", callback_data="admin_quest_create"))
    kb.add(InlineKeyboardButton(text="📋 Список квестов", callback_data="admin_quest_list"))
    kb.add(InlineKeyboardButton(text="🗑️ Удалить квест", callback_data="admin_quest_delete"))
    kb.add(InlineKeyboardButton(text="📊 Статистика квестов", callback_data="admin_quest_stats"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"📜 <b>Управление квестами</b>\n\n"
        f"📋 Всего квестов: {len(quests)}\n"
        f"👥 Активных участников: {sum(len(uq) for uq in user_quests.values())}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_quest_create")
async def admin_quest_create(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📜 <b>Создание квеста — Шаг 1/3</b>\n\n"
        "Введите название квеста:"
    )
    await state.set_state(AdminStates.waiting_for_quest_name)
    await callback.answer()


@router.message(AdminStates.waiting_for_quest_name)
async def process_quest_name(message: types.Message, state: FSMContext):
    await state.update_data(quest_name=message.text.strip())
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🎴 Дропы", callback_data="quest_goal_drops"))
    kb.add(InlineKeyboardButton(text="🔄 Обмены", callback_data="quest_goal_trades"))
    kb.add(InlineKeyboardButton(text="🛒 Покупки", callback_data="quest_goal_purchases"))
    kb.add(InlineKeyboardButton(text="📦 Собрать карты", callback_data="quest_goal_collect"))
    kb.adjust(2)
    
    await message.answer(
        f"📜 <b>Создание квеста — Шаг 2/3</b>\n\n"
        f"Название: {message.text}\n\n"
        f"Выберите тип цели:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(AdminStates.waiting_for_quest_goal)


@router.callback_query(lambda c: c.data.startswith("quest_goal_"), AdminStates.waiting_for_quest_goal)
async def process_quest_goal(callback: types.CallbackQuery, state: FSMContext):
    goal_type = callback.data.replace("quest_goal_", "")
    await state.update_data(quest_goal_type=goal_type)
    
    await callback.message.answer(
        f"📜 <b>Создание квеста — Шаг 3/3</b>\n\n"
        f"Введите данные в формате:\n"
        f"<code>цель | награда_токенов | card_id (опц) | дней</code>\n\n"
        f"Пример: <code>10 | 100 | | 7</code> — 10 дропов, 100🎫, 7 дней\n"
        f"Пример с картой: <code>5 | 50 | card_123 | 3</code>"
    )
    await state.set_state(AdminStates.waiting_for_quest_reward)
    await callback.answer()


@router.message(AdminStates.waiting_for_quest_reward)
async def process_quest_reward(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split("|")
        goal = int(parts[0].strip())
        tokens = int(parts[1].strip())
        card_id = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        days = int(parts[3].strip()) if len(parts) > 3 else 7
        
        data = await state.get_data()
        
        quest_id = f"quest_{int(datetime.now().timestamp())}"
        quest = Quest(
            quest_id=quest_id,
            name=data["quest_name"],
            description=f"Выполни цель и получи награду!",
            goal_type=data["quest_goal_type"],
            goal_target=goal,
            reward_tokens=tokens,
            reward_card_id=card_id,
            duration_days=days
        )
        
        quests[quest_id] = quest
        save_extended_data()
        log_admin_action(message.from_user.id, "create_quest", quest_id, quest.name)
        
        reward_text = f"{tokens}🎫"
        if card_id and card_id in cards:
            reward_text += f" + {cards[card_id].name}"
        
        await message.answer(
            f"✅ <b>Квест создан!</b>\n\n"
            f"📜 {quest.name}\n"
            f"🎯 Цель: {goal} ({quest.goal_type})\n"
            f"🎁 Награда: {reward_text}\n"
            f"⏳ Срок: {days} дней\n"
            f"🆔 <code>{quest_id}</code>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_quest_list")
async def admin_quest_list(callback: types.CallbackQuery):
    if not quests:
        await callback.answer("Нет квестов!", show_alert=True)
        return
    
    text = "📜 <b>Список квестов</b>\n\n"
    for qid, quest in list(quests.items())[:15]:
        completions = sum(1 for uq in user_quests.values() if qid in uq and uq[qid].completed)
        text += f"• <b>{quest.name}</b>\n"
        text += f"  🎯 {quest.goal_target} ({quest.goal_type})\n"
        text += f"  🎁 {quest.reward_tokens}🎫\n"
        text += f"  ✅ Выполнили: {completions}\n"
        text += f"  🆔 <code>{qid}</code>\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_quests_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_quest_stats")
async def admin_quest_stats(callback: types.CallbackQuery):
    total_participants = len(user_quests)
    total_completions = sum(1 for uq in user_quests.values() for q in uq.values() if q.completed)
    
    text = (
        f"📊 <b>Статистика квестов</b>\n\n"
        f"👥 Участников: {total_participants}\n"
        f"✅ Выполнено квестов: {total_completions}\n"
        f"📋 Активных квестов: {len(quests)}\n\n"
    )
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_quests_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# 4.2 ДОСТИЖЕНИЯ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_achievements_menu")
async def admin_achievements_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🏆 Создать достижение", callback_data="admin_achievement_create"))
    kb.add(InlineKeyboardButton(text="📋 Список достижений", callback_data="admin_achievement_list"))
    kb.add(InlineKeyboardButton(text="🗑️ Удалить достижение", callback_data="admin_achievement_delete"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"🏆 <b>Управление достижениями</b>\n\n"
        f"📋 Всего достижений: {len(achievements)}\n"
        f"👥 Игроков с достижениями: {len(user_achievements)}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_achievement_create")
async def admin_achievement_create(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🏆 <b>Создание достижения — Шаг 1/2</b>\n\n"
        "Введите название достижения:"
    )
    await state.set_state(AdminStates.waiting_for_achievement_name)
    await callback.answer()


@router.message(AdminStates.waiting_for_achievement_name)
async def process_achievement_name(message: types.Message, state: FSMContext):
    await state.update_data(achievement_name=message.text.strip())
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🎴 Всего дропов", callback_data="ach_cond_drops"))
    kb.add(InlineKeyboardButton(text="🔄 Всего обменов", callback_data="ach_cond_trades"))
    kb.add(InlineKeyboardButton(text="🎫 Накопить токенов", callback_data="ach_cond_tokens"))
    kb.add(InlineKeyboardButton(text="📦 Собрать карт", callback_data="ach_cond_cards"))
    kb.add(InlineKeyboardButton(text="🎮 Достичь уровня", callback_data="ach_cond_level"))
    kb.adjust(2)
    
    await message.answer(
        f"🏆 <b>Создание достижения — Шаг 2/2</b>\n\n"
        f"Название: {message.text}\n\n"
        f"Выберите тип условия:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(AdminStates.waiting_for_achievement_condition)


@router.callback_query(lambda c: c.data.startswith("ach_cond_"), AdminStates.waiting_for_achievement_condition)
async def process_achievement_condition(callback: types.CallbackQuery, state: FSMContext):
    cond_type = callback.data.replace("ach_cond_", "")
    await state.update_data(achievement_cond=cond_type)
    
    await callback.message.answer(
        f"Введите целевое значение и награду в формате:\n"
        f"<code>значение | токены | значок</code>\n\n"
        f"Пример: <code>100 | 500 | 🎖️</code>"
    )
    await state.set_state(AdminStates.waiting_for_quest_reward)  # переиспользуем
    await callback.answer()


@router.message(AdminStates.waiting_for_quest_reward)
async def process_achievement_final(message: types.Message, state: FSMContext):
    # Проверяем, что это достижение, а не квест
    data = await state.get_data()
    if "achievement_name" not in data:
        return  # это квест, обрабатывается другим хендлером
    
    try:
        parts = message.text.strip().split("|")
        value = int(parts[0].strip())
        tokens = int(parts[1].strip())
        badge = parts[2].strip() if len(parts) > 2 else "🏆"
        
        ach_id = f"ach_{int(datetime.now().timestamp())}"
        achievement = Achievement(
            achievement_id=ach_id,
            name=data["achievement_name"],
            description=f"Достигните {value} {data['achievement_cond']}",
            condition_type=data["achievement_cond"],
            condition_value=value,
            reward_tokens=tokens,
            reward_badge=badge
        )
        
        achievements[ach_id] = achievement
        save_extended_data()
        log_admin_action(message.from_user.id, "create_achievement", ach_id, achievement.name)
        
        await message.answer(
            f"✅ <b>Достижение создано!</b>\n\n"
            f"🏆 {achievement.name}\n"
            f"📊 Условие: {value} ({achievement.condition_type})\n"
            f"🎁 Награда: {tokens}🎫 {badge}\n"
            f"🆔 <code>{ach_id}</code>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_achievement_list")
async def admin_achievement_list(callback: types.CallbackQuery):
    if not achievements:
        await callback.answer("Нет достижений!", show_alert=True)
        return
    
    text = "🏆 <b>Список достижений</b>\n\n"
    for aid, ach in list(achievements.items())[:15]:
        unlocked = sum(1 for ua in user_achievements.values() if aid in ua)
        text += f"{ach.reward_badge} <b>{ach.name}</b>\n"
        text += f"  📊 {ach.condition_value} ({ach.condition_type})\n"
        text += f"  🎁 {ach.reward_tokens}🎫\n"
        text += f"  👥 Разблокировали: {unlocked}\n"
        text += f"  🆔 <code>{aid}</code>\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

    # ════════════════════════════════════════════════════════════════════════════════
# 4.3 МИНИ-ИГРЫ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_minigames_menu")
async def admin_minigames_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    for game_id, game in minigames.items():
        status = "✅" if game.enabled else "❌"
        kb.add(InlineKeyboardButton(
            text=f"{status} {game.name}",
            callback_data=f"admin_minigame_{game_id}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    text = "🎲 <b>Управление мини-играми</b>\n\n"
    for game in minigames.values():
        text += f"{'✅' if game.enabled else '❌'} <b>{game.name}</b>\n"
        text += f"  💰 Ставка: {game.min_bet}-{game.max_bet}🎫\n"
        text += f"  🎲 Шанс: {game.win_chance}% | Множ: x{game.multiplier}\n"
        text += f"  💎 Джекпот: {game.jackpot}🎫\n\n"
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin_minigame_"))
async def admin_minigame_config(callback: types.CallbackQuery, state: FSMContext):
    game_id = callback.data.replace("admin_minigame_", "")
    game = minigames.get(game_id)
    
    if not game:
        await callback.answer("Игра не найдена!", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(
        text=f"{'✅' if game.enabled else '❌'} Вкл/выкл",
        callback_data=f"minigame_toggle_{game_id}"
    ))
    kb.add(InlineKeyboardButton(text="💰 Изменить ставки", callback_data=f"minigame_bets_{game_id}"))
    kb.add(InlineKeyboardButton(text="🎲 Изменить шанс", callback_data=f"minigame_chance_{game_id}"))
    kb.add(InlineKeyboardButton(text="💎 Сбросить джекпот", callback_data=f"minigame_reset_jackpot_{game_id}"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_minigames_menu"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"🎲 <b>{game.name}</b>\n\n"
        f"Статус: {'✅ Вкл' if game.enabled else '❌ Выкл'}\n"
        f"Ставки: {game.min_bet}-{game.max_bet}🎫\n"
        f"Шанс победы: {game.win_chance}%\n"
        f"Множитель: x{game.multiplier}\n"
        f"Джекпот: {game.jackpot}🎫\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("minigame_toggle_"))
async def minigame_toggle(callback: types.CallbackQuery):
    game_id = callback.data.replace("minigame_toggle_", "")
    game = minigames.get(game_id)
    if game:
        game.enabled = not game.enabled
        save_extended_data()
        log_admin_action(callback.from_user.id, "toggle_minigame", game_id, str(game.enabled))
    await admin_minigame_config(callback, None)


@router.callback_query(lambda c: c.data.startswith("minigame_reset_jackpot_"))
async def minigame_reset_jackpot(callback: types.CallbackQuery):
    game_id = callback.data.replace("minigame_reset_jackpot_", "")
    game = minigames.get(game_id)
    if game:
        game.jackpot = 0
        save_extended_data()
        log_admin_action(callback.from_user.id, "reset_jackpot", game_id)
        await callback.answer("✅ Джекпот сброшен!", show_alert=True)
    await admin_minigame_config(callback, None)


# ════════════════════════════════════════════════════════════════════════════════
# 5.1 A/B ТЕСТЫ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_ab_tests_menu")
async def admin_ab_tests_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🧪 Создать A/B тест", callback_data="admin_ab_test_create"))
    kb.add(InlineKeyboardButton(text="📋 Список тестов", callback_data="admin_ab_test_list"))
    kb.add(InlineKeyboardButton(text="⏹️ Остановить тест", callback_data="admin_ab_test_stop"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    active = sum(1 for t in ab_tests.values() if t.active)
    
    await callback.message.edit_text(
        f"🧪 <b>A/B Тесты</b>\n\n"
        f"📊 Всего тестов: {len(ab_tests)}\n"
        f"🟢 Активных: {active}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_ab_test_create")
async def admin_ab_test_create(callback: types.CallbackQuery, state: FSMContext):
    # Показываем доступные товары
    items_text = "🎴 <b>Карточки:</b>\n"
    for cid, card in list(cards.items())[:5]:
        items_text += f"• <code>{cid}</code>: {card.name}\n"
    
    items_text += "\n📦 <b>Лутбоксы:</b>\n"
    if lootboxes:
        for lid, lb in list(lootboxes.items())[:5]:
            items_text += f"• <code>{lid}</code>: {lb.get('name', lid)}\n"
    
    await callback.message.answer(
        f"🧪 <b>Создание A/B теста</b>\n\n"
        f"{items_text}\n"
        f"Введите данные в формате:\n"
        f"<code>название | тип | id | цена_A | цена_B</code>\n\n"
        f"Пример: <code>Тест лутбокса | lootbox | lb_123 | 199 | 149</code>"
    )
    await state.set_state(AdminStates.waiting_for_ab_test_prices)
    await callback.answer()


@router.message(AdminStates.waiting_for_ab_test_prices)
async def process_ab_test(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split("|")
        name = parts[0].strip()
        item_type = parts[1].strip()
        item_id = parts[2].strip()
        price_a = int(parts[3].strip())
        price_b = int(parts[4].strip())
        
        test_id = f"ab_{int(datetime.now().timestamp())}"
        test = ABTest(
            test_id=test_id,
            name=name,
            item_type=item_type,
            item_id=item_id,
            group_a_price=price_a,
            group_b_price=price_b
        )
        
        ab_tests[test_id] = test
        save_extended_data()
        log_admin_action(message.from_user.id, "create_ab_test", test_id, name)
        
        await message.answer(
            f"✅ <b>A/B тест создан!</b>\n\n"
            f"🧪 {name}\n"
            f"📦 {item_type}: {item_id}\n"
            f"🅰️ Группа A: {price_a}₽\n"
            f"🅱️ Группа B: {price_b}₽\n"
            f"🆔 <code>{test_id}</code>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка формата: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_ab_test_list")
async def admin_ab_test_list(callback: types.CallbackQuery):
    if not ab_tests:
        await callback.answer("Нет A/B тестов!", show_alert=True)
        return
    
    text = "🧪 <b>A/B Тесты</b>\n\n"
    for tid, test in list(ab_tests.items())[:10]:
        status = "🟢" if test.active else "🔴"
        conv_a = (test.group_a_conversions / max(test.group_a_conversions + test.group_b_conversions, 1)) * 100
        text += f"{status} <b>{test.name}</b>\n"
        text += f"  🅰️ A: {test.group_a_price}₽ — {test.group_a_conversions} конв.\n"
        text += f"  🅱️ B: {test.group_b_price}₽ — {test.group_b_conversions} конв.\n"
        text += f"  💰 A: {test.group_a_revenue}₽ | B: {test.group_b_revenue}₽\n"
        text += f"  🆔 <code>{tid}</code>\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_ab_tests_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# 6.3 БЕКАПЫ (SNAPSHOTS)
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_snapshot_menu")
async def admin_snapshot_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    snapshots = list(SNAPSHOTS_DIR.glob("snapshot_*.json"))
    snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="💾 Создать бекап", callback_data="admin_snapshot_create"))
    
    if snapshots:
        kb.add(InlineKeyboardButton(text="📋 Список бекапов", callback_data="admin_snapshot_list"))
        kb.add(InlineKeyboardButton(text="🔄 Восстановить", callback_data="admin_snapshot_restore"))
        kb.add(InlineKeyboardButton(text="🗑️ Удалить старые", callback_data="admin_snapshot_cleanup"))
    
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"💾 <b>Управление бекапами</b>\n\n"
        f"📦 Бекапов: {len(snapshots)}\n"
        f"📁 Папка: {SNAPSHOTS_DIR}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_snapshot_create")
async def admin_snapshot_create(callback: types.CallbackQuery):
    # Сохраняем текущее состояние
    save_data()
    save_extended_data()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = SNAPSHOTS_DIR / f"snapshot_{timestamp}.json"
    
    # Копируем основной файл базы
    if USERS_FILE.exists():
        shutil.copy(USERS_FILE, snapshot_file)
    
    log_admin_action(callback.from_user.id, "create_snapshot", None, timestamp)
    
    await callback.answer(f"✅ Бекап создан: snapshot_{timestamp}.json", show_alert=True)
    await admin_snapshot_menu(callback)


@router.callback_query(lambda c: c.data == "admin_snapshot_list")
async def admin_snapshot_list(callback: types.CallbackQuery):
    snapshots = list(SNAPSHOTS_DIR.glob("snapshot_*.json"))
    snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not snapshots:
        await callback.answer("Нет бекапов!", show_alert=True)
        return
    
    text = "💾 <b>Список бекапов</b>\n\n"
    for snap in snapshots[:15]:
        mtime = datetime.fromtimestamp(snap.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
        size = snap.stat().st_size // 1024
        text += f"• {snap.name}\n  {mtime} | {size} KB\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_snapshot_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_snapshot_cleanup")
async def admin_snapshot_cleanup(callback: types.CallbackQuery):
    snapshots = list(SNAPSHOTS_DIR.glob("snapshot_*.json"))
    snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Оставляем последние 10
    deleted = 0
    for snap in snapshots[10:]:
        snap.unlink()
        deleted += 1
    
    log_admin_action(callback.from_user.id, "cleanup_snapshots", None, f"deleted {deleted}")
    await callback.answer(f"✅ Удалено {deleted} старых бекапов!", show_alert=True)
    await admin_snapshot_menu(callback)


# ════════════════════════════════════════════════════════════════════════════════
# 10.1 ОПРОСЫ
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_polls_menu")
async def admin_polls_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    active_polls = sum(1 for p in polls.values() if p.active)
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📋 Создать опрос", callback_data="admin_poll_create"))
    kb.add(InlineKeyboardButton(text="📊 Список опросов", callback_data="admin_poll_list"))
    kb.add(InlineKeyboardButton(text="⏹️ Завершить опрос", callback_data="admin_poll_stop"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"📋 <b>Управление опросами</b>\n\n"
        f"📊 Всего: {len(polls)}\n"
        f"🟢 Активных: {active_polls}\n\n"
        f"Выберите действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_poll_create")
async def admin_poll_create(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📋 <b>Создание опроса — Шаг 1/2</b>\n\n"
        "Введите вопрос опроса:"
    )
    await state.set_state(AdminStates.waiting_for_poll_question)
    await callback.answer()


@router.message(AdminStates.waiting_for_poll_question)
async def process_poll_question(message: types.Message, state: FSMContext):
    await state.update_data(poll_question=message.text.strip())
    
    await message.answer(
        f"📋 <b>Создание опроса — Шаг 2/2</b>\n\n"
        f"Вопрос: {message.text}\n\n"
        f"Введите варианты ответов через |\n"
        f"Пример: <code>Вариант 1 | Вариант 2 | Вариант 3</code>"
    )
    await state.set_state(AdminStates.waiting_for_poll_options)


@router.message(AdminStates.waiting_for_poll_options)
async def process_poll_options(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        options = [opt.strip() for opt in message.text.split("|")]
        
        poll_id = f"poll_{int(datetime.now().timestamp())}"
        poll = Poll(
            poll_id=poll_id,
            question=data["poll_question"],
            options=options,
            votes={opt: 0 for opt in options}
        )
        
        polls[poll_id] = poll
        save_extended_data()
        log_admin_action(message.from_user.id, "create_poll", poll_id, poll.question)
        
        await message.answer(
            f"✅ <b>Опрос создан!</b>\n\n"
            f"📋 {poll.question}\n"
            f"📊 Вариантов: {len(options)}\n"
            f"🆔 <code>{poll_id}</code>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_poll_list")
async def admin_poll_list(callback: types.CallbackQuery):
    if not polls:
        await callback.answer("Нет опросов!", show_alert=True)
        return
    
    text = "📋 <b>Список опросов</b>\n\n"
    for pid, poll in list(polls.items())[:10]:
        status = "🟢" if poll.active else "🔴"
        total_votes = sum(poll.votes.values())
        text += f"{status} <b>{poll.question}</b>\n"
        text += f"  Голосов: {total_votes}\n"
        for opt, votes in poll.votes.items():
            pct = (votes / total_votes * 100) if total_votes else 0
            text += f"    • {opt}: {votes} ({pct:.1f}%)\n"
        text += f"  🆔 <code>{pid}</code>\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_polls_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# 11.1 КАСТОМНЫЕ ТЕКСТЫ БОТА
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_custom_texts")
async def admin_custom_texts_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    for key in custom_texts.keys():
        kb.add(InlineKeyboardButton(
            text=f"✏️ {key}",
            callback_data=f"admin_edit_text_{key}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    kb.adjust(1)
    
    text = "✏️ <b>Редактор текстов бота</b>\n\n"
    for key, value in custom_texts.items():
        preview = value[:50] + "..." if len(value) > 50 else value
        text += f"<b>{key}</b>: {preview}\n\n"
    
    text += "Выберите текст для редактирования:"
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin_edit_text_"))
async def admin_edit_text(callback: types.CallbackQuery, state: FSMContext):
    key = callback.data.replace("admin_edit_text_", "")
    current = custom_texts.get(key, "")
    
    await state.update_data(edit_text_key=key)
    
    await callback.message.answer(
        f"✏️ <b>Редактирование: {key}</b>\n\n"
        f"Текущий текст:\n<code>{current}</code>\n\n"
        f"Введите новый текст:\n"
        f"<i>Можно использовать: {'{username}'}, {'{time}'}, {'{card_name}'}, {'{rarity}'}</i>"
    )
    await state.set_state(AdminStates.waiting_for_custom_text_value)
    await callback.answer()


@router.message(AdminStates.waiting_for_custom_text_value)
async def process_custom_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("edit_text_key")
    
    if key:
        custom_texts[key] = message.text
        save_extended_data()
        log_admin_action(message.from_user.id, "edit_custom_text", key)
        await message.answer(f"✅ Текст '{key}' обновлён!")
    
    await state.clear()


# ════════════════════════════════════════════════════════════════════════════════
# ОБЩИЕ ОБРАБОТЧИКИ (back, save, restart)
# ════════════════════════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "admin_back")
async def admin_back_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await cmd_admin(callback.message)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_force_save")
async def admin_force_save(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    save_data()
    save_admin_data()
    save_extended_data()
    log_admin_action(callback.from_user.id, "force_save")
    await callback.answer("✅ Все данные сохранены!", show_alert=True)


@router.callback_query(lambda c: c.data == "admin_restart")
async def admin_restart_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    save_data()
    save_admin_data()
    save_extended_data()
    log_admin_action(callback.from_user.id, "restart_bot")
    await callback.answer("✅ Данные сохранены! Перезапуск...", show_alert=True)
    
    os._exit(0)


# ─── Функция для выполнения отложенных задач (вызывать из main.py в фоне) ───────
async def check_scheduled_tasks():
    """Проверка и выполнение отложенных задач (вызывать в фоне)"""
    while True:
        try:
            now = datetime.now()
            for task in scheduled_tasks:
                if task.get("status") != "pending":
                    continue
                
                exec_time = datetime.fromisoformat(task["exec_time"])
                if exec_time <= now:
                    # Выполняем задачу
                    if task["type"] == "tokens":
                        amount = int(task["value"])
                        target = task["target"]
                        
                        if target == "all":
                            for user in users.values():
                                if not user.is_banned:
                                    user.tokens += amount
                            logger.info(f"Scheduled: Gave {amount} tokens to all")
                        else:
                            user = get_user_by_username(target)
                            if user:
                                user.tokens += amount
                                logger.info(f"Scheduled: Gave {amount} tokens to {target}")
                    
                    elif task["type"] == "card":
                        card_id = task["value"]
                        target = task["target"]
                        card = cards.get(card_id)
                        
                        if card:
                            if target == "all":
                                for user in users.values():
                                    if not user.is_banned:
                                        user.cards[card_id] = user.cards.get(card_id, 0) + 1
                                logger.info(f"Scheduled: Gave {card.name} to all")
                            else:
                                user = get_user_by_username(target)
                                if user:
                                    user.cards[card_id] = user.cards.get(card_id, 0) + 1
                                    logger.info(f"Scheduled: Gave {card.name} to {target}")
                    
                    task["status"] = "completed"
                    task["completed_at"] = now.isoformat()
                    save_extended_data()
                    save_data()
            
            await asyncio.sleep(30)  # Проверка каждые 30 секунд
        except Exception as e:
            logger.error(f"Error in scheduled tasks: {e}")
            await asyncio.sleep(60)
