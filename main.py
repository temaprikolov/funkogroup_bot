# main.py — ПОЛНАЯ ВЕРСИЯ с исправлениями и новыми функциями
import asyncio
import json
import logging
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import *
from games import GameStats, GameChallenge, FortuneWheel, DailyWheel, determine_rps_winner, play_slots
from promo import PromoCodeManager
from states import AdminStates, TradeStates, OrderStates, GameStates, WheelBuyState
from models import (NotificationSettings, User, Card, ShopItem, Order, ExclusiveCard,
                    WeeklyEvent, ReferralContest)
from aiogram.types import LabeledPrice

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("❌ Токен бота не настроен!")
    exit(1)

DATA_DIR = Path("data")
IMAGES_DIR = DATA_DIR / "images"
VIDEOS_DIR = DATA_DIR / "videos"
DATA_DIR.mkdir(exist_ok=True); IMAGES_DIR.mkdir(exist_ok=True); VIDEOS_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
CARDS_FILE = DATA_DIR / "cards.json"
TRADES_FILE = DATA_DIR / "trades.json"
SHOP_FILE = DATA_DIR / "shop.json"
ORDERS_FILE = DATA_DIR / "orders.json"
LEVELS_FILE = DATA_DIR / "levels.json"
EXCLUSIVES_FILE = DATA_DIR / "exclusives.json"
POPULARITY_FILE = DATA_DIR / "popularity.json"
PROMO_FILE = DATA_DIR / "promos.json"
WHEEL_FILE = DATA_DIR / "wheel.json"
EVENT_FILE = DATA_DIR / "event.json"
REFERRAL_CONTEST_FILE = DATA_DIR / "referral_contest.json"

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ── Глобальные хранилища ──────────────────────────────────────────────────────
users: Dict[int, User] = {}
cards: Dict[str, Card] = {}
card_pool: List[str] = []
premium_card_pool: List[str] = []
trades: Dict[str, Dict] = {}
user_inventory_pages: Dict[int, Dict] = {}
shop_items: Dict[str, ShopItem] = {}
orders: Dict[str, Order] = {}
exclusive_cards: Dict[str, ExclusiveCard] = {}
card_popularity: Dict[str, Dict] = {}
active_game_challenges: Dict[str, GameChallenge] = {}
current_wheel: Optional[FortuneWheel] = None
promo_manager: Optional[PromoCodeManager] = None
current_weekly_event: Optional[WeeklyEvent] = None
current_referral_contest: Optional[ReferralContest] = None
user_message_times: Dict[int, List] = defaultdict(list)


# ════════════════════════════════════════════════════════════════════════════════
# Вспомогательные функции
# ════════════════════════════════════════════════════════════════════════════════
def get_level_discount(level: int) -> int:
    return min((level // 15) * 2, 20)

def get_price_with_discount(original_price: int, level: int) -> int:
    d = get_level_discount(level)
    return max(original_price * (100 - d) // 100, 1) if d else original_price

def get_token_price(ruble_price: int) -> int:
    tp = ruble_price * 1.5
    return int(tp) + (1 if tp % 1 else 0)

def is_video_card(card: Card) -> bool:
    return bool(card.image_filename and card.image_filename.endswith('.mp4'))

def get_video_path(card: Card) -> Optional[Path]:
    if not card.image_filename or not card.image_filename.endswith('.mp4'):
        return None
    fp = VIDEOS_DIR / card.image_filename
    return fp if fp.exists() else None

def get_image_path(card: Card) -> Optional[Path]:
    if not card.image_filename: return None
    fp = (VIDEOS_DIR if is_video_card(card) else IMAGES_DIR) / card.image_filename
    return fp if fp.exists() else None

def get_rarity_color(rarity: str) -> str:
    return {"basic": "⚪️", "cool": "🔵", "legendary": "🟡", "vinyl figure": "🟣"}.get(rarity, "⚪️")

def get_rarity_name(rarity: str) -> str:
    return {"basic": "Обычная", "cool": "Крутая", "legendary": "Легендарная",
            "vinyl figure": "Виниловая фигурка"}.get(rarity, rarity)

def update_user_interaction(user: User):
    now = datetime.now().isoformat()
    user.last_seen = now; user.last_interaction = now

def get_user_by_username(username: str) -> Optional[User]:
    if not username: return None
    username = username.lstrip('@').lower()
    for u in users.values():
        if u.username.lower() == username:
            return u
    return None

def check_spam(user_id: int) -> bool:
    now = datetime.now().timestamp()
    user_message_times[user_id] = [t for t in user_message_times[user_id] if now - t < TIME_WINDOW]
    if len(user_message_times[user_id]) >= MESSAGE_LIMIT:
        return True
    user_message_times[user_id].append(now)
    return False

def is_user_banned(user: User) -> Tuple[bool, Optional[str]]:
    if not user.is_banned: return False, None
    if user.banned_until:
        until = datetime.fromisoformat(user.banned_until)
        if until <= datetime.now():
            user.is_banned = False; user.ban_reason = None; user.banned_until = None
            save_data(); return False, None
        left = until - datetime.now()
        return True, f"Забанен до {until.strftime('%d.%m.%Y %H:%M')}. Причина: {user.ban_reason}"
    return True, f"Забанен навсегда. Причина: {user.ban_reason}"

def is_user_frozen(user: User) -> Tuple[bool, Optional[str]]:
    if not user.is_frozen: return False, None
    if user.frozen_until:
        until = datetime.fromisoformat(user.frozen_until)
        if until <= datetime.now():
            user.is_frozen = False; user.frozen_until = None
            save_data(); return False, None
        return True, f"Аккаунт заморожен до {until.strftime('%d.%m.%Y %H:%M')}"
    return True, "Аккаунт заморожен"

def check_user_access(user: User) -> Tuple[bool, Optional[str]]:
    banned, reason = is_user_banned(user)
    if banned: return False, reason
    frozen, reason = is_user_frozen(user)
    if frozen: return False, reason
    return True, None

async def check_access_before_handle(message_or_callback, user_id: int) -> bool:
    user = get_or_create_user(user_id)
    ok, reason = check_user_access(user)
    if not ok:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(f"⛔ <b>Доступ запрещен!</b>\n\n{reason}")
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(f"⛔ {reason}", show_alert=True)
        return False
    if isinstance(message_or_callback, types.Message) and user_id not in ADMIN_IDS:
        if check_spam(user_id):
            await message_or_callback.answer("⚠️ Слишком много сообщений. Подождите.")
            return False
    return True

async def check_subscription(user_id: int) -> bool:
    """Проверяет подписку. При любой ошибке — возвращает True (не блокируем пользователя)."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # "left" и "kicked" — точно не подписан; всё остальное (member, administrator, creator, restricted) — подписан
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logger.warning(f"check_subscription error for {user_id}: {e} — assuming subscribed")
        return True   # При ошибке не блокируем


# ════════════════════════════════════════════════════════════════════════════════
# Уровни и опыт
# ════════════════════════════════════════════════════════════════════════════════
def calculate_level_exp(level: int) -> int:
    return int(LEVEL_SETTINGS['base_exp_per_level'] * (LEVEL_SETTINGS['exp_multiplier'] ** (level - 1)))

def add_experience(user: User, action_type: str, amount: int = None):
    if not LEVEL_SETTINGS['enabled']: return
    if amount is None:
        amount = LEVEL_SETTINGS['exp_actions'].get(action_type, 0)
    user.experience += amount; user.total_exp_earned += amount
    exp_needed = calculate_level_exp(user.level)
    while user.experience >= exp_needed and user.level < 100:
        user.experience -= exp_needed; user.level += 1
        exp_needed = calculate_level_exp(user.level)
    # save_data() убран из add_experience — вызывающий код сохраняет сам

def get_cooldown_by_level(user: User, is_premium: bool = None) -> float:
    if is_premium is None: is_premium = user.is_premium
    base_minutes = (2 if is_premium else 4) * 60
    return max(base_minutes - (user.level - 1) * 2, 30) / 60

def get_level_progress_bar(user: User, length: int = 10) -> str:
    exp_needed = calculate_level_exp(user.level)
    filled = int((user.experience / exp_needed) * length)
    pct = (user.experience / exp_needed) * 100
    return "▰" * filled + "▱" * (length - filled) + f" {pct:.1f}%"

def get_card_cooldown_hours(user: User) -> int:
    if user.has_reduced_cd and user.reduced_cd_until:
        if datetime.fromisoformat(user.reduced_cd_until) > datetime.now():
            return 2
    return 4

def get_trade_cooldown_hours(user: User) -> int:
    if user.has_reduced_trade_cd and user.reduced_trade_cd_until:
        if datetime.fromisoformat(user.reduced_trade_cd_until) > datetime.now():
            return 2
    return 4

def can_open_card(user: User) -> Tuple[bool, Optional[str]]:
    if user.skip_card_cooldown_available: return True, None
    if not user.last_card_time: return True, None
    remaining = timedelta(hours=get_card_cooldown_hours(user)) - (datetime.now() - datetime.fromisoformat(user.last_card_time))
    if remaining.total_seconds() <= 0: return True, None
    h = int(remaining.total_seconds() // 3600)
    m = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{h}ч {m}м"

def can_trade(user: User) -> Tuple[bool, Optional[str]]:
    if user.skip_trade_cooldown_available: return True, None
    if not user.last_trade_time: return True, None
    remaining = timedelta(hours=get_trade_cooldown_hours(user)) - (datetime.now() - datetime.fromisoformat(user.last_trade_time))
    if remaining.total_seconds() <= 0: return True, None
    h = int(remaining.total_seconds() // 3600)
    m = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{h}ч {m}м"

def update_card_popularity(card_id: str, action: str = "view"):
    if card_id not in card_popularity:
        card_popularity[card_id] = {'purchases': 0, 'views': 0, 'last_purchased': None}
    if action == "purchase":
        card_popularity[card_id]['purchases'] += 1
        card_popularity[card_id]['last_purchased'] = datetime.now().isoformat()
    elif action == "view":
        card_popularity[card_id]['views'] += 1

def get_popular_cards(limit: int = 5) -> List[Dict]:
    popular = []
    for cid, stats in card_popularity.items():
        card = cards.get(cid)
        if card:
            popular.append({'card': card, 'stats': stats, 'score': stats['purchases'] * 3 + stats['views']})
    popular.sort(key=lambda x: x['score'], reverse=True)
    return popular[:limit]

def get_top_spenders(period_days: int = 30, limit: int = 10) -> List[Dict]:
    ago = datetime.now() - timedelta(days=period_days)
    spenders = []
    for user in users.values():
        user_orders = [o for o in orders.values()
                       if o.user_id == user.user_id and o.status == "confirmed"
                       and datetime.fromisoformat(o.confirmed_at or o.created_at) >= ago]
        total = sum(o.price for o in user_orders)
        if total > 0:
            spenders.append({'user': user, 'total_spent': total, 'orders_count': len(user_orders)})
    spenders.sort(key=lambda x: x['total_spent'], reverse=True)
    return spenders[:limit]

def get_personal_recommendations(user_id: int, limit: int = 3) -> List[Dict]:
    user = users.get(user_id)
    if not user or not user.cards: return []
    purchased = list(user.cards.keys())
    rarities = defaultdict(int)
    for cid in purchased:
        c = cards.get(cid)
        if c: rarities[c.rarity] += 1
    if not rarities: return []
    fav = max(rarities.items(), key=lambda x: x[1])[0]
    recs = []
    for cid, card in cards.items():
        if cid not in purchased and card.rarity == fav and cid in shop_items:
            recs.append({'card': card, 'price': shop_items[cid].price, 'reason': f"Любимая редкость: {get_rarity_name(fav)}"})
    recs.sort(key=lambda x: card_popularity.get(x['card'].card_id, {}).get('purchases', 0), reverse=True)
    return recs[:limit]


# ════════════════════════════════════════════════════════════════════════════════
# Пользователи
# ════════════════════════════════════════════════════════════════════════════════
def get_or_create_user(user_id: int, username: str = "", first_name: str = "", referrer_id: int = None) -> User:
    if user_id not in users:
        users[user_id] = User(user_id, username, first_name)
        if referrer_id and referrer_id in users and referrer_id != user_id:
            users[referrer_id].referrals.append(user_id)
            users[referrer_id].referral_contest_month_refs += 1
            users[user_id].referrer_id = referrer_id
            add_experience(users[referrer_id], 'referral', 50)
            add_experience(users[user_id], 'welcome_bonus', 100)
            asyncio.create_task(send_new_referral_notification(referrer_id, user_id))
            ref_count = len(users[referrer_id].referrals)
            if ref_count % 3 == 0 and card_pool:
                cid = random.choice(card_pool)
                users[referrer_id].cards[cid] = users[referrer_id].cards.get(cid, 0) + 1
                asyncio.create_task(send_referral_bonus(referrer_id, ref_count, cid))
        save_data()
    else:
        if username and users[user_id].username != username:
            users[user_id].username = username
        if first_name and users[user_id].first_name != first_name:
            users[user_id].first_name = first_name
    update_user_interaction(users[user_id])
    return users[user_id]


def add_premium(user: User, days: int = 30):
    user.is_premium = True
    now = datetime.now()
    if user.premium_until:
        until = datetime.fromisoformat(user.premium_until)
        user.premium_until = ((until if until > now else now) + timedelta(days=days)).isoformat()
    else:
        user.premium_until = (now + timedelta(days=days)).isoformat()
    for _ in range(10):
        result = open_card(user)
    update_user_interaction(user)
    save_data()
    return True

def add_reduced_cd(user: User, days: int = 30):
    user.has_reduced_cd = True
    now = datetime.now()
    if user.reduced_cd_until:
        until = datetime.fromisoformat(user.reduced_cd_until)
        user.reduced_cd_until = ((until if until > now else now) + timedelta(days=days)).isoformat()
    else:
        user.reduced_cd_until = (now + timedelta(days=days)).isoformat()
    update_user_interaction(user); save_data(); return True

def add_reduced_trade_cd(user: User, days: int = 30):
    user.has_reduced_trade_cd = True
    now = datetime.now()
    if user.reduced_trade_cd_until:
        until = datetime.fromisoformat(user.reduced_trade_cd_until)
        user.reduced_trade_cd_until = ((until if until > now else now) + timedelta(days=days)).isoformat()
    else:
        user.reduced_trade_cd_until = (now + timedelta(days=days)).isoformat()
    update_user_interaction(user); save_data(); return True

def add_cooldown(user: User, hours: int):
    user.last_card_time = datetime.now().isoformat()
    update_user_interaction(user); save_data(); return True

def ban_user(user: User, reason: str = "Нарушение правил", days: int = 0):
    user.is_banned = True; user.ban_reason = reason
    user.banned_until = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None
    save_data(); return True


# ════════════════════════════════════════════════════════════════════════════════
# Открытие карточек
# ════════════════════════════════════════════════════════════════════════════════
def update_card_pool():
    global card_pool, premium_card_pool
    card_pool = []; premium_card_pool = []
    weights = {"basic": 9790, "cool": 1000, "legendary": 150, "vinyl figure": 60}
    prem_weights = {"basic": 9710, "cool": 1000, "legendary": 200, "vinyl figure": 90}
    for cid, card in cards.items():
        w = weights.get(card.rarity, 1)
        pw = prem_weights.get(card.rarity, 1)
        card_pool.extend([cid] * w)
        premium_card_pool.extend([cid] * pw)
    logger.info(f"✅ Пул обновлён: {len(card_pool)} / {len(premium_card_pool)}")

def open_card(user: User) -> Optional[Tuple[Card, str]]:
    pool = premium_card_pool if (user.is_premium and premium_card_pool) else card_pool
    if not pool: return None
    card_id = random.choice(pool)
    card = cards[card_id]
    user.cards[card_id] = user.cards.get(card_id, 0) + 1
    user.opened_packs += 1
    if user.skip_card_cooldown_available:
        user.skip_card_cooldown_available = False
    else:
        user.last_card_time = datetime.now().isoformat()
    user.tokens += 3 if user.is_premium else 1
    update_user_interaction(user)
    add_experience(user, 'open_card')
    # Ивент
    add_event_score(user.user_id, "open_cards")
    if card.rarity == "legendary":
        add_event_score(user.user_id, "collect_legendaries")
    save_data()
    return card, card_id

def claim_daily_bonus(user: User) -> bool:
    if not user.is_premium: return False
    today = datetime.now().date().isoformat()
    if user.daily_bonus_claimed == today: return False
    for _ in range(3):
        open_card(user)
    user.daily_bonus_claimed = today
    update_user_interaction(user); save_data(); return True


# ════════════════════════════════════════════════════════════════════════════════
# Ивенты
# ════════════════════════════════════════════════════════════════════════════════
def add_event_score(user_id: int, event_type: str, amount: int = 1):
    global current_weekly_event
    if not current_weekly_event: return
    if current_weekly_event.event_type != event_type: return
    if datetime.fromisoformat(current_weekly_event.end_time) < datetime.now(): return
    current_weekly_event.add_score(user_id, amount)


# ════════════════════════════════════════════════════════════════════════════════
# Магазин
# ════════════════════════════════════════════════════════════════════════════════
def generate_shop_card() -> Optional[Tuple[str, int]]:
    if not cards: return None
    rarity_weights = {"basic": 100, "cool": 30, "legendary": 7, "vinyl figure": 1}
    by_rarity = defaultdict(list)
    for cid, c in cards.items():
        by_rarity[c.rarity].append(cid)
    pool = []
    for rarity, w in rarity_weights.items():
        if by_rarity[rarity]:
            pool.extend([rarity] * w)
    if not pool: return None
    rarity = random.choice(pool)
    cid = random.choice(by_rarity[rarity])
    # Применяем динамическую скидку с шансом
    price = SHOP_PRICES.get(rarity, 53)
    return cid, price

def maybe_add_skip_items_to_shop():
    now = datetime.now()
    if not any(item.card_id in ["skip_card_cooldown", "skip_trade_cooldown"] for item in shop_items.values()):
        if random.random() < 0.3:
            t = random.choice(["card", "trade", "both"])
            if t in ["card", "both"]:
                k = f"skip_card_cooldown_{int(now.timestamp())}"
                shop_items[k] = ShopItem(card_id="skip_card_cooldown", price=SKIP_CARD_COOLDOWN_COST,
                                         expires_at=(now + timedelta(hours=12)).isoformat())
            if t in ["trade", "both"]:
                k = f"skip_trade_cooldown_{int(now.timestamp())}"
                shop_items[k] = ShopItem(card_id="skip_trade_cooldown", price=SKIP_TRADE_COOLDOWN_COST,
                                         expires_at=(now + timedelta(hours=12)).isoformat())

def update_shop():
    global shop_items
    now = datetime.now()
    expired = [k for k, item in shop_items.items() if datetime.fromisoformat(item.expires_at) <= now]
    for k in expired:
        del shop_items[k]
    regular_count = sum(1 for item in shop_items.values() if not item.card_id.startswith('skip_'))
    updated = False
    while regular_count < 3:
        result = generate_shop_card()
        if not result: break
        cid, price = result
        if cid not in shop_items:
            shop_items[cid] = ShopItem(card_id=cid, price=price, expires_at=(now + timedelta(hours=12)).isoformat())
            regular_count += 1; updated = True
        else:
            break
    maybe_add_skip_items_to_shop()
    if updated:
        asyncio.create_task(notify_shop_update())
    save_data()

def apply_flash_discount_to_shop():
    """Применяем случайную флэш-скидку к одному товару."""
    now = datetime.now()
    regular = [(k, item) for k, item in shop_items.items() if not k.startswith('skip_')]
    if not regular: return
    k, item = random.choice(regular)
    if hasattr(item, 'flash_sale_until') and item.flash_sale_until:
        if datetime.fromisoformat(item.flash_sale_until) > now:
            return  # уже есть флэш
    discount_rub = random.randint(10, DYNAMIC_PRICE_DISCOUNT_MAX)
    duration_min = random.randint(DYNAMIC_PRICE_MIN_MINUTES, DYNAMIC_PRICE_MAX_MINUTES)
    item.original_price = item.price
    item.price = max(item.price - discount_rub, 1)
    item.flash_sale_until = (now + timedelta(minutes=duration_min)).isoformat()
    save_data()
    logger.info(f"🔥 Флэш-скидка на {k}: -{discount_rub}₽ на {duration_min} мин")

def restore_flash_prices():
    """Возвращаем цены после флэш-скидок."""
    now = datetime.now()
    changed = False
    for k, item in list(shop_items.items()):
        if hasattr(item, 'flash_sale_until') and item.flash_sale_until:
            if datetime.fromisoformat(item.flash_sale_until) <= now:
                if hasattr(item, 'original_price') and item.original_price:
                    item.price = item.original_price
                item.flash_sale_until = None
                changed = True
    if changed: save_data()

def create_order(user: User, card_id: str, price: int, gift_to_user_id: int = None) -> Optional[Order]:
    order_id = f"order_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, card_id, price, gift_to_user_id=gift_to_user_id)
    orders[order_id] = order
    if card_id in shop_items and not card_id.startswith('skip_'):
        del shop_items[card_id]
    add_experience(user, 'purchase_card', price // 10)
    save_data()
    return order

def confirm_order(order_id: str, admin_id: int) -> bool:
    if order_id not in orders: return False
    order = orders[order_id]
    if order.status != "pending": return False

    # Определяем, кому выдать товар
    recipient_id = order.gift_to_user_id if order.gift_to_user_id else order.user_id
    recipient = users.get(recipient_id)
    payer = users.get(order.user_id)
    if not payer: return False

    order.status = "confirmed"
    order.confirmed_at = datetime.now().isoformat()
    order.admin_id = admin_id
    payer.orders_confirmed_count = getattr(payer, 'orders_confirmed_count', 0) + 1

    special_ids = ["skip_card_cooldown", "skip_trade_cooldown", "buy_level_1", "buy_level_5"]

    if order.card_id == "skip_card_cooldown":
        (recipient or payer).skip_card_cooldown_available = True
    elif order.card_id == "skip_trade_cooldown":
        (recipient or payer).skip_trade_cooldown_available = True
    elif order.card_id == "buy_level_1":
        add_experience(payer, 'purchase_card', calculate_level_exp(payer.level) - payer.experience)
    elif order.card_id == "buy_level_5":
        for _ in range(5):
            if payer.level < 100:
                add_experience(payer, 'purchase_card', calculate_level_exp(payer.level) - payer.experience)
    elif order.card_id.startswith("lootbox_"):
        # Лутбокс — открываем паки
        key = order.card_id.replace("lootbox_", "")
        info = LOOTBOX_PRICES.get(key)
        target = recipient or payer
        if info and cards:
            guaranteed = [cid for cid, c in cards.items() if c.rarity == info["guaranteed"]]
            if guaranteed:
                gid = random.choice(guaranteed)
                target.cards[gid] = target.cards.get(gid, 0) + 1
            for _ in range(info["cards"] - 1):
                pool_w = []
                for cid, c in cards.items():
                    pool_w.extend([cid] * {"basic": 70, "cool": 20, "legendary": 8, "vinyl figure": 2}.get(c.rarity, 1))
                if pool_w:
                    cid = random.choice(pool_w)
                    target.cards[cid] = target.cards.get(cid, 0) + 1
            target.opened_packs += info["cards"]
    else:
        c = cards.get(order.card_id)
        if not c: return False
        target = recipient or payer
        target.cards[order.card_id] = target.cards.get(order.card_id, 0) + 1
        target.opened_packs += 1
        target.tokens += 3 if target.is_premium else 1
        update_card_popularity(order.card_id, "purchase")

    update_user_interaction(payer)
    save_data()
    return True

def reject_order(order_id: str, admin_id: int) -> bool:
    if order_id not in orders: return False
    order = orders[order_id]
    if order.status != "pending": return False
    order.status = "rejected"
    order.confirmed_at = datetime.now().isoformat()
    order.admin_id = admin_id
    if order.card_id not in ["skip_card_cooldown","skip_trade_cooldown","buy_level_1","buy_level_5"] \
       and not order.card_id.startswith("lootbox_"):
        if sum(1 for item in shop_items.values() if not item.card_id.startswith('skip_')) < 3:
            shop_items[order.card_id] = ShopItem(card_id=order.card_id, price=SHOP_PRICES.get(
                cards.get(order.card_id, Card('','','basic')).rarity, 53),
                expires_at=(datetime.now() + timedelta(hours=12)).isoformat())
    save_data()
    return True

def create_trade(from_user_id: int, to_user_id: int, cards_to_give: List[str]) -> str:
    trade_id = f"trade_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    trades[trade_id] = {
        'id': trade_id, 'from_user': from_user_id, 'to_user': to_user_id,
        'cards': cards_to_give, 'status': 'pending',
        'created_at': datetime.now().isoformat(), 'receiver_card': None, 'completed_at': None
    }
    save_data()
    return trade_id


# ════════════════════════════════════════════════════════════════════════════════
# Колесо фортуны (большое)
# ════════════════════════════════════════════════════════════════════════════════
async def draw_wheel_winners():
    global current_wheel
    if not current_wheel or datetime.now() < current_wheel.end_time: return
    if not current_wheel.participants:
        current_wheel = FortuneWheel(); save_data(); return
    winners = current_wheel.draw_winners(cards)
    for winner_id, prizes in winners.items():
        user = users.get(winner_id)
        if not user: continue
        msg = "🎡 <b>Колесо фортуны: Вы выиграли!</b>\n\n"
        for prize_type, amount, name, card_id in prizes:
            msg += f"• {name}"
            if prize_type == 'tokens':
                user.tokens += amount; msg += f": +{amount}🎫\n"
            elif prize_type in ['skip_card', 'skip_trade']:
                if prize_type == 'skip_card': user.skip_card_cooldown_available = True
                else: user.skip_trade_cooldown_available = True
                msg += f": {amount} шт.\n"
            elif prize_type in ['cool_card', 'legendary_card', 'vinyl_card'] and card_id:
                user.cards[card_id] = user.cards.get(card_id, 0) + 1
                c = cards.get(card_id)
                msg += f": {c.name if c else name}\n"
        save_data()
        try: await bot.send_message(winner_id, msg)
        except: pass
    current_wheel = FortuneWheel(); save_data()


# ════════════════════════════════════════════════════════════════════════════════
# Секретный магазин
# ════════════════════════════════════════════════════════════════════════════════
async def maybe_send_secret_shop_notification():
    """Раз в час: случайно рассылаем уведомление о секретном магазине."""
    now = datetime.now()
    eligible = [u for u in users.values() if not u.is_banned and not u.is_frozen
                and (not u.last_secret_shop_notified or
                     (now - datetime.fromisoformat(u.last_secret_shop_notified)).days >= SECRET_SHOP_COOLDOWN_DAYS)]
    if not eligible: return
    # Шанс = 5% на каждого eligible пользователя
    chosen = [u for u in eligible if random.random() < 0.05]
    if not chosen: return
    chosen = chosen[:3]  # не больше 3 уведомлений за раз
    for user in chosen:
        user.last_secret_shop_notified = now.isoformat()
        user.secret_shop_expires = (now + timedelta(minutes=SECRET_SHOP_DURATION_MINUTES)).isoformat()
        save_data()
        try:
            await bot.send_message(
                user.user_id,
                "🤫 <b>Секретный магазин открыт!</b>\n\n"
                f"Только для вас — специальные скидки до {SECRET_SHOP_DISCOUNT_MAX}%!\n"
                f"⏰ Доступен ещё {SECRET_SHOP_DURATION_MINUTES} минут.\n\n"
                "Кнопка появилась в главном меню → нажмите <b>🤫МАГАЗИН🤫</b>!"
            )
        except: pass


async def notify_shop_update():
    try:
        msg = "🛒 <b>МАГАЗИН ОБНОВЛЕН!</b>\n\nПоявились новые карточки! 🎴\n\n"
        for cid, item in shop_items.items():
            card = cards.get(cid)
            if card and not cid.startswith('skip_'):
                msg += f"{get_rarity_color(card.rarity)} {card.name} — {item.price}₽\n"
        msg += "\n⏰ Торопитесь, карточки исчезнут через 12 часов!"
        sent = 0
        for uid, user in users.items():
            if user.notification_settings.shop_updates and not user.is_banned and not user.is_frozen:
                try:
                    await bot.send_message(uid, msg); sent += 1; await asyncio.sleep(0.05)
                except: pass
        try: await bot.send_message(CHANNEL_ID, msg)
        except: pass
        logger.info(f"✅ Уведомления магазина: {sent}")
    except Exception as e:
        logger.error(f"Ошибка notify_shop_update: {e}")

async def send_order_notification(order_id: str, user_id: int, card_name: str, price: int):
    try:
        await bot.send_message(user_id,
            f"🎉 <b>Заказ подтверждён!</b>\n\n🆔 {order_id}\n🎴 {card_name}\n💰 {price}₽\n\n✅ Товар в инвентаре!")
    except Exception as e:
        logger.error(f"Ошибка уведомления заказа {order_id}: {e}")

async def send_referral_bonus(user_id: int, count: int, card_id: str):
    try:
        card = cards.get(card_id)
        card_name = card.name if card else "карточка"
        await bot.send_message(user_id,
            f"🎉 <b>Бонус за {count} рефералов!</b>\n\n🎴 Получена: <b>{card_name}</b>")
    except: pass

async def send_new_referral_notification(user_id: int, new_ref_id: int):
    try:
        new_user = users.get(new_ref_id)
        user = users.get(user_id)
        if not user or not new_user: return
        total = len(user.referrals)
        next_bonus = 3 - (total % 3) if total % 3 else 3
        await bot.send_message(user_id,
            f"🎉 @{new_user.username} присоединился по вашей ссылке!\n"
            f"👥 Всего рефералов: {total}\n🎯 До карточки: {next_bonus}")
    except: pass


# ════════════════════════════════════════════════════════════════════════════════
# Клавиатуры
# ════════════════════════════════════════════════════════════════════════════════
def get_main_menu(user: User = None):
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="👤 Профиль"))
    kb.add(KeyboardButton(text="💝 Поддержать проект"))
    kb.add(KeyboardButton(text="🎴 Инвентарь"))
    kb.add(KeyboardButton(text="🔄 Обмен"))
    kb.add(KeyboardButton(text="🛒 Магазин"))
    kb.add(KeyboardButton(text="🎪 Эксклюзивы"))
    kb.add(KeyboardButton(text="Игры🕹"))
    kb.add(KeyboardButton(text="🎡 Колесо фортуны"))
    kb.add(KeyboardButton(text="🏆 Топ игроков"))
    kb.add(KeyboardButton(text="⚗️ Прокачка"))
    kb.add(KeyboardButton(text="❓ Помощь"))
    # Секретный магазин — динамически
    if user and hasattr(user, 'secret_shop_expires') and user.secret_shop_expires:
        if datetime.fromisoformat(user.secret_shop_expires) > datetime.now():
            kb.add(KeyboardButton(text="🤫МАГАЗИН🤫"))
    kb.adjust(3, 3, 3, 2)
    return kb.as_markup(resize_keyboard=True)

def get_subscription_keyboard():
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK))
    kb.add(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))
    return kb.as_markup()


# ════════════════════════════════════════════════════════════════════════════════
# Показ методов оплаты
# ════════════════════════════════════════════════════════════════════════════════
async def show_payment_methods(callback: types.CallbackQuery, product_type: str, product_id: str,
                               price: int, stars_price: int, description: str = "", level: int = 1):
    dp_price = get_price_with_discount(price, level)
    discount = get_level_discount(level)
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🏦 Перевод на Т-Банк",
                                callback_data=f"payment_method:transfer:{product_type}:{product_id}:{dp_price}"))
    kb.add(InlineKeyboardButton(text="🔗 Оплата по ссылке",
                                callback_data=f"payment_method:link:{product_type}:{product_id}:{dp_price}"))
    kb.add(InlineKeyboardButton(text=f"⭐ Купить за {stars_price} звёзд",
                                callback_data=f"payment_method:stars:{product_type}:{product_id}:{stars_price}"))
    kb.add(InlineKeyboardButton(text="👨‍💼 Через администратора",
                                callback_data=f"payment_method:admin:{product_type}:{product_id}:{dp_price}"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(1)
    disc_text = f"\n🎁 Скидка {discount}%: {price}₽ → {dp_price}₽" if discount else ""
    await callback.message.answer(
        f"💵 <b>Выберите способ оплаты</b>\n\n"
        f"🎁 {description}\n💰 {price}₽{disc_text}\n\n"
        f"После оплаты рублями используйте /payment\nПри оплате звёздами — автоматически.",
        reply_markup=kb.as_markup()
    )


# ════════════════════════════════════════════════════════════════════════════════
# Сохранение/загрузка данных
# ════════════════════════════════════════════════════════════════════════════════
def load_data():
    global users, cards, card_pool, trades, shop_items, orders, exclusive_cards
    global card_popularity, current_wheel, promo_manager, current_weekly_event, current_referral_contest
    try:
        if USERS_FILE.exists():
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                ud = json.load(f)
            for uid_str, d in ud.items():
                uid = int(uid_str)
                u = User(uid, d.get('username',''), d.get('first_name',''))
                for k, v in d.items():
                    if k == 'notification_settings':
                        ns = NotificationSettings()
                        for nk, nv in v.items():
                            setattr(ns, nk, nv)
                        u.notification_settings = ns
                    elif k == 'game_stats':
                        u.game_stats = GameStats()
                        u.game_stats.rock_paper_scissors = v.get('rock_paper_scissors', u.game_stats.rock_paper_scissors)
                        u.game_stats.dice = v.get('dice', u.game_stats.dice)
                        u.game_stats.slots = v.get('slots', u.game_stats.slots)
                    elif hasattr(u, k):
                        setattr(u, k, v)
                users[uid] = u

        if CARDS_FILE.exists():
            with open(CARDS_FILE, 'r', encoding='utf-8') as f:
                cd = json.load(f)
            for cid, d in cd.items():
                cards[cid] = Card(cid, d['name'], d['rarity'], d.get('image_filename',''))
        else:
            cards["fanco1"] = Card("fanco1", "FUNKO CARD - BASIC", "basic")

        if TRADES_FILE.exists():
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                trades.update(json.load(f))

        if SHOP_FILE.exists():
            with open(SHOP_FILE, 'r', encoding='utf-8') as f:
                sd = json.load(f)
            for k, d in sd.items():
                item = ShopItem(k, d['price'], d['expires_at'])
                item.original_price = d.get('original_price', d['price'])
                item.flash_sale_until = d.get('flash_sale_until')
                shop_items[k] = item

        if ORDERS_FILE.exists():
            with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
                od = json.load(f)
            for oid, d in od.items():
                o = Order(oid, d['user_id'], d['card_id'], d['price'], d['status'],
                          gift_to_user_id=d.get('gift_to_user_id'))
                o.created_at = d.get('created_at', datetime.now().isoformat())
                o.confirmed_at = d.get('confirmed_at')
                o.admin_id = d.get('admin_id')
                o.payment_proof = d.get('payment_proof')
                orders[oid] = o

        if LEVELS_FILE.exists():
            with open(LEVELS_FILE, 'r', encoding='utf-8') as f:
                ld = json.load(f)
            for uid_str, d in ld.items():
                uid = int(uid_str)
                if uid in users:
                    users[uid].level = d.get('level', 1)
                    users[uid].experience = d.get('experience', 0)
                    users[uid].total_exp_earned = d.get('total_exp_earned', 0)

        if EXCLUSIVES_FILE.exists():
            with open(EXCLUSIVES_FILE, 'r', encoding='utf-8') as f:
                ed = json.load(f)
            for cid, d in ed.items():
                exc = ExclusiveCard(cid, d['total_copies'], d['price'], d.get('end_date'))
                exc.sold_copies = d.get('sold_copies', 0)
                exc.is_active = d.get('is_active', True)
                exc.flash_sale_until = d.get('flash_sale_until')
                exclusive_cards[cid] = exc

        if POPULARITY_FILE.exists():
            with open(POPULARITY_FILE, 'r', encoding='utf-8') as f:
                card_popularity.update(json.load(f))

        if WHEEL_FILE.exists():
            with open(WHEEL_FILE, 'r', encoding='utf-8') as f:
                wd = json.load(f)
            current_wheel = FortuneWheel()
            current_wheel.wheel_id = wd.get('wheel_id', current_wheel.wheel_id)
            current_wheel.start_time = datetime.fromisoformat(wd['start_time'])
            current_wheel.end_time = datetime.fromisoformat(wd['end_time'])
            current_wheel.participants = {int(k): v for k, v in wd.get('participants', {}).items()}
        if not current_wheel:
            current_wheel = FortuneWheel()

        if EVENT_FILE.exists():
            with open(EVENT_FILE, 'r', encoding='utf-8') as f:
                current_weekly_event = WeeklyEvent.from_dict(json.load(f))
        if not current_weekly_event:
            from events import new_weekly_event
            current_weekly_event = new_weekly_event()

        if REFERRAL_CONTEST_FILE.exists():
            with open(REFERRAL_CONTEST_FILE, 'r', encoding='utf-8') as f:
                current_referral_contest = ReferralContest.from_dict(json.load(f))
        if not current_referral_contest:
            from events import new_referral_contest
            current_referral_contest = new_referral_contest(1)

        promo_manager = PromoCodeManager(PROMO_FILE)
        update_card_pool()
        logger.info(f"✅ Загружено: {len(users)} юзеров, {len(cards)} карточек, {len(orders)} заказов")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")
        import traceback; traceback.print_exc()
        if not cards:
            cards["fanco1"] = Card("fanco1", "FUNKO CARD - BASIC", "basic")
        if not current_wheel:
            current_wheel = FortuneWheel()
        if not promo_manager:
            promo_manager = PromoCodeManager(PROMO_FILE)
        update_card_pool()

def save_data():
    try:
        # Users
        ud = {}
        for uid, u in users.items():
            ud[str(uid)] = {
                'username': u.username, 'first_name': u.first_name, 'cards': u.cards,
                'opened_packs': u.opened_packs, 'created_at': u.created_at,
                'last_seen': u.last_seen, 'last_interaction': u.last_interaction,
                'is_premium': u.is_premium, 'premium_until': u.premium_until,
                'has_reduced_cd': u.has_reduced_cd, 'reduced_cd_until': u.reduced_cd_until,
                'has_reduced_trade_cd': u.has_reduced_trade_cd, 'reduced_trade_cd_until': u.reduced_trade_cd_until,
                'last_card_time': u.last_card_time, 'last_trade_time': u.last_trade_time,
                'daily_bonus_claimed': u.daily_bonus_claimed, 'daily_wheel_claimed': u.daily_wheel_claimed,
                'last_shop_check': u.last_shop_check, 'last_reminder_sent': u.last_reminder_sent,
                'is_banned': u.is_banned, 'ban_reason': u.ban_reason, 'banned_until': u.banned_until,
                'is_frozen': u.is_frozen, 'frozen_until': u.frozen_until,
                'level': u.level, 'experience': u.experience, 'total_exp_earned': u.total_exp_earned,
                'secret_total_spent': u.secret_total_spent, 'referrals': u.referrals,
                'referrer_id': u.referrer_id, 'referral_bonus_claimed': u.referral_bonus_claimed,
                'tokens': u.tokens, 'last_lucky_dice_time': u.last_lucky_dice_time,
                'last_secret_shop_notified': getattr(u, 'last_secret_shop_notified', None),
                'secret_shop_expires': getattr(u, 'secret_shop_expires', None),
                'referral_contest_season': getattr(u, 'referral_contest_season', 0),
                'referral_contest_month_refs': getattr(u, 'referral_contest_month_refs', 0),
                'event_contributions': getattr(u, 'event_contributions', {}),
                'active_title': getattr(u, 'active_title', 'Новичок'),
                'unlocked_titles': getattr(u, 'unlocked_titles', ['Новичок']),
                'orders_confirmed_count': getattr(u, 'orders_confirmed_count', 0),
                'notification_settings': {
                    'shop_updates': u.notification_settings.shop_updates,
                    'card_available': u.notification_settings.card_available,
                    'promo_offers': u.notification_settings.promo_offers,
                    'trade_offers': u.notification_settings.trade_offers,
                    'system_messages': u.notification_settings.system_messages,
                },
                'skip_card_cooldown_available': u.skip_card_cooldown_available,
                'skip_trade_cooldown_available': u.skip_trade_cooldown_available,
                'game_stats': {
                    'rock_paper_scissors': u.game_stats.rock_paper_scissors,
                    'dice': u.game_stats.dice, 'slots': u.game_stats.slots,
                }
            }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(ud, f, ensure_ascii=False, indent=2)

        with open(CARDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({cid: {'name': c.name, 'rarity': c.rarity, 'image_filename': c.image_filename}
                       for cid, c in cards.items()}, f, ensure_ascii=False, indent=2)

        with open(TRADES_FILE, 'w', encoding='utf-8') as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)

        with open(SHOP_FILE, 'w', encoding='utf-8') as f:
            json.dump({k: {'price': item.price, 'expires_at': item.expires_at,
                           'original_price': getattr(item, 'original_price', item.price),
                           'flash_sale_until': getattr(item, 'flash_sale_until', None)}
                       for k, item in shop_items.items()}, f, ensure_ascii=False, indent=2)

        with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({oid: {'user_id': o.user_id, 'card_id': o.card_id, 'price': o.price,
                             'status': o.status, 'created_at': o.created_at,
                             'confirmed_at': o.confirmed_at, 'admin_id': o.admin_id,
                             'payment_proof': o.payment_proof,
                             'gift_to_user_id': getattr(o, 'gift_to_user_id', None)}
                       for oid, o in orders.items()}, f, ensure_ascii=False, indent=2)

        with open(LEVELS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(uid): {'level': u.level, 'experience': u.experience,
                                  'total_exp_earned': u.total_exp_earned,
                                  'secret_total_spent': u.secret_total_spent}
                       for uid, u in users.items()}, f, ensure_ascii=False, indent=2)

        with open(EXCLUSIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump({cid: {'total_copies': e.total_copies, 'sold_copies': e.sold_copies,
                             'price': e.price, 'end_date': e.end_date, 'is_active': e.is_active,
                             'flash_sale_until': getattr(e, 'flash_sale_until', None)}
                       for cid, e in exclusive_cards.items()}, f, ensure_ascii=False, indent=2)

        with open(POPULARITY_FILE, 'w', encoding='utf-8') as f:
            json.dump(card_popularity, f, ensure_ascii=False, indent=2)

        if current_wheel:
            with open(WHEEL_FILE, 'w', encoding='utf-8') as f:
                json.dump({'wheel_id': current_wheel.wheel_id,
                           'start_time': current_wheel.start_time.isoformat(),
                           'end_time': current_wheel.end_time.isoformat(),
                           'participants': current_wheel.participants}, f, ensure_ascii=False, indent=2)

        if current_weekly_event:
            with open(EVENT_FILE, 'w', encoding='utf-8') as f:
                json.dump(current_weekly_event.to_dict(), f, ensure_ascii=False, indent=2)

        if current_referral_contest:
            with open(REFERRAL_CONTEST_FILE, 'w', encoding='utf-8') as f:
                json.dump(current_referral_contest.to_dict(), f, ensure_ascii=False, indent=2)

        if promo_manager:
            promo_manager.save()

    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")
        import traceback; traceback.print_exc()


# ════════════════════════════════════════════════════════════════════════════════
# Платёжные обработчики
# ════════════════════════════════════════════════════════════════════════════════
@dp.pre_checkout_query()
async def pre_checkout_handler(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(':')
    if len(parts) < 4: return
    product_type = parts[0]
    user_id_str = parts[2]
    product_id = parts[1]

    # Обработка покупки билетов за звёзды
    if product_type == "wheel_tickets":
        try:
            ticket_count = int(product_id)
            user = users.get(int(user_id_str))
            if user:
                current_wheel.add_tickets(user.user_id, ticket_count)
                save_data()
                await message.answer(
                    f"✅ <b>Куплено {ticket_count} билет(а)!</b>\n\n"
                    f"🎟 Ваших билетов в колесе: {current_wheel.participants.get(user.user_id, 0)}\n"
                    f"Удачи в розыгрыше! 🍀"
                )
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id,
                            f"⭐ @{user.username} купил {ticket_count} билетов колеса за {ticket_count}⭐")
                    except: pass
        except Exception as e:
            logger.error(f"Ошибка обработки билетов колеса: {e}")
        return

    user = users.get(int(user_id_str))
    if not user: return
    if product_type == "premium":
        add_premium(user, 30); await message.answer("✅ Премиум активирован!")
    elif product_type == "reduced_cd":
        add_reduced_cd(user, 30); await message.answer("✅ Уменьшенный кулдаун карточек активирован!")
    elif product_type == "reduced_trade_cd":
        add_reduced_trade_cd(user, 30); await message.answer("✅ Уменьшенный кулдаун обменов активирован!")
    elif product_type in ["shop_card", "exclusive_card"]:
        card = cards.get(product_id)
        if card:
            user.cards[product_id] = user.cards.get(product_id, 0) + 1
            user.opened_packs += 1
            await message.answer(f"✅ Карточка {card.name} добавлена!")
    elif product_type == "skip_card":
        user.skip_card_cooldown_available = True; await message.answer("✅ Скип кулдауна карточки!")
    elif product_type == "skip_trade":
        user.skip_trade_cooldown_available = True; await message.answer("✅ Скип кулдауна обменов!")
    save_data()
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"⭐ @{user.username} оплатил {product_type} звёздами. "
                f"Сумма: {message.successful_payment.total_amount}⭐")
        except: pass


# ════════════════════════════════════════════════════════════════════════════════
# Команды
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    referrer_id = None
    if len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith('ref_'):
            try:
                rid = int(args[4:])
                if rid != user_id and rid >= 1000: referrer_id = rid
            except: pass
    user = get_or_create_user(user_id, message.from_user.username or "",
                              message.from_user.first_name or "", referrer_id)
    if not await check_access_before_handle(message, user_id): return
    # Только для новых пользователей проверяем подписку
    # (check_subscription возвращает True при ошибке API — не блокируем)
    is_new_user = user_id not in users or len(users.get(user_id, User(user_id)).cards) == 0
    if is_new_user and not await check_subscription(user_id):
        await message.answer(
            "👋 <b>Добро пожаловать в Funko Cards!</b>\n\n"
            f"⚠️ Подпишитесь на наш канал: {CHANNEL_LINK}\n\n"
            "1. Нажмите «Подписаться»\n2. Подпишитесь\n3. Нажмите «Я подписался»",
            reply_markup=get_subscription_keyboard()
        ); return
    if user.is_premium:
        if claim_daily_bonus(user):
            await message.answer("🎁 Ежедневный бонус: 3 карточки получены!")
    await message.answer(
        "🎮 <b>Добро пожаловать в мир карточек Фанко!</b>\n\n"
        "🎴 Напишите <b>фанко</b> в групповом чате чтобы получить карточку!\n\n"
        "📱 <b>Меню:</b>\n"
        "• Профиль, инвентарь, обмены\n"
        "• Магазин, эксклюзивы, лутбоксы 📦\n"
        "• Игры на карточки и токены 🎮\n"
        "• Колесо фортуны 🎡\n"
        "• ⚗️ Прокачка карточек (крафт)\n"
        "• 🎉 Еженедельные ивенты и реферальный конкурс",
        reply_markup=get_main_menu(user)
    )

@dp.callback_query(lambda c: c.data == "check_subscription")
async def process_check_subscription(callback: types.CallbackQuery):
    # Подписка проверяется при /start
    user = get_or_create_user(callback.from_user.id, callback.from_user.username or "")
    await callback.message.edit_text("✅ Подписка подтверждена!")
    await callback.message.answer("🎮 <b>Добро пожаловать!</b>", reply_markup=get_main_menu(user))
    await callback.answer()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id)
    await message.answer(
        "❓ <b>Справка</b>\n\n"
        "🎴 Пишите <b>фанко</b> в групповом чате — получаете карточки!\n\n"
        "🎮 <b>Игры:</b> КНБ, Дайс, Автоматы, Кубик удачи\n"
        "⚗️ <b>Прокачка:</b> 3 обычные → крутая, 3 крутые → легендарная\n"
        "📦 <b>Лутбоксы:</b> Магазин → Лутбоксы\n"
        "🎡 <b>Колесо фортуны:</b> покупайте билеты за токены\n"
        "🎰 <b>Ежедневное колесо:</b> бесплатный спин раз в день\n"
        "🎉 <b>Ивенты:</b> каждую неделю новый челлендж\n"
        "🏆 <b>Реферальный конкурс:</b> топ пригласивших в Топ игроков\n\n"
        "Команды: /start /help /promo /invite /myorders /payment /refresh\n\n"
        f"Скидка за уровень {user.level}: {get_level_discount(user.level)}%"
    )

@dp.message(Command("promo"))
async def promo_command(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /promo [код]"); return
    code = args[1].upper().strip()
    user = get_or_create_user(message.from_user.id)
    if not promo_manager:
        await message.answer("❌ Система промокодов недоступна."); return
    promo = promo_manager.use_promo(code, user.user_id)
    if not promo:
        await message.answer("❌ <b>Промокод недействителен или уже использован!</b>"); return
    reward_text = ""
    if promo.reward_type == "card":
        card = cards.get(promo.reward_value)
        if card:
            user.cards[promo.reward_value] = user.cards.get(promo.reward_value, 0) + 1
            reward_text = f"🎴 {card.name}"
    elif promo.reward_type == "tokens":
        try:
            amount = int(promo.reward_value)
            user.tokens += amount
            reward_text = f"🎫 {amount} токенов"
        except: reward_text = "🎫 Токены"
    elif promo.reward_type == "reset_trade":
        user.skip_trade_cooldown_available = True; reward_text = "🔄 Сброс кулдауна обменов"
    elif promo.reward_type == "reset_card":
        user.skip_card_cooldown_available = True; reward_text = "⚡ Сброс кулдауна карточек"
    elif promo.reward_type == "premium_3d":
        add_premium(user, 3); reward_text = "💎 Премиум на 3 дня"
    save_data()
    await message.answer(f"✅ <b>Промокод активирован!</b>\n\n🎁 Получено: {reward_text}")

@dp.message(Command("invite"))
async def invite_command(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user.user_id}"
    total = len(user.referrals)
    cards_earned = total // 3
    next_bonus = 3 - (total % 3) if total % 3 else 3
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📢 Поделиться",
                                url=f"https://t.me/share/url?url={link}&text=🎴 Присоединяйся к Funko Cards!"))
    kb.add(InlineKeyboardButton(text="🏆 Реф. конкурс", callback_data="referral_contest"))
    kb.adjust(1)
    await message.answer(
        f"🎁 <b>Приглашай друзей!</b>\n\n"
        f"👥 Приглашено: {total}\n🎴 Карточек получено: {cards_earned}\n"
        f"🎯 До следующей карточки: {next_bonus}\n\n"
        f"📢 Ваша ссылка:\n<code>{link}</code>",
        reply_markup=kb.as_markup(), disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data == "referral_contest")
async def referral_contest_handler(callback: types.CallbackQuery):
    from events import get_referral_contest_top
    top = get_referral_contest_top(10)
    user = get_or_create_user(callback.from_user.id)
    end_str = ""
    if current_referral_contest:
        end = datetime.fromisoformat(current_referral_contest.end_time)
        days_left = (end - datetime.now()).days
        end_str = f"\n⏰ До конца сезона: {days_left} дней"
    r = f"🏆 <b>Реферальный конкурс</b>{end_str}\n\n<b>Топ-10:</b>\n"
    for i, (uid, refs) in enumerate(top, 1):
        u = users.get(uid)
        name = f"@{u.username}" if u else f"ID:{uid}"
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} {name}: {refs} реф.\n"
    my_refs = user.referral_contest_month_refs
    my_pos = next((i+1 for i, (uid, _) in enumerate(top) if uid == user.user_id), None)
    r += f"\n👤 Вы: {my_refs} рефералов в этом месяце"
    if my_pos: r += f" (место {my_pos})"
    r += "\n\n<b>Призы:</b>\n🥇 100🎫 + 1 виниловая + премиум 30д\n🥈 75🎫 + 2 лег. + скипы\n🥉 50🎫 + 1 лег. + скипы\n4-10: 25🎫 + скипы"
    await callback.answer()
    await callback.message.answer(r)

@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id)
    user_orders = sorted([o for o in orders.values() if o.user_id == user.user_id],
                         key=lambda o: o.created_at, reverse=True)
    if not user_orders:
        await message.answer("📋 У вас пока нет заказов."); return
    r = f"📋 <b>Ваши заказы ({len(user_orders)})</b>\n\n"
    status_map = {"pending": "⏳", "confirmed": "✅", "rejected": "❌"}
    for o in user_orders[:10]:
        card_name = o.card_id
        c = cards.get(o.card_id)
        if c: card_name = c.name
        elif o.card_id == "skip_card_cooldown": card_name = "⚡ Скип карточки"
        elif o.card_id == "skip_trade_cooldown": card_name = "🔄 Скип обмена"
        elif o.card_id.startswith("lootbox_"): card_name = f"📦 {o.card_id}"
        dt = datetime.fromisoformat(o.created_at).strftime('%d.%m.%Y %H:%M')
        gift_text = ""
        if getattr(o, 'gift_to_user_id', None):
            gift_user = users.get(o.gift_to_user_id)
            gift_text = f" → 🎁 @{gift_user.username if gift_user else '?'}"
        r += f"{status_map.get(o.status,'❓')} <code>{o.order_id}</code>\n{card_name}{gift_text} | {o.price}₽ | {dt}\n\n"
    await message.answer(r)

@dp.message(Command("refresh"))
async def cmd_refresh(message: types.Message, state: FSMContext):
    if not await state.get_state():
        await message.answer("🔄 Нет активных действий."); return
    await state.clear()
    await message.answer("✅ Действие отменено!")

@dp.message(Command("payment"))
async def payment_proof_command(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id): return
    await message.answer("📤 Введите номер заказа (например: order_12345_6789):")
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(OrderStates.waiting_for_payment_proof, F.text)
async def process_order_id(message: types.Message, state: FSMContext):
    oid = message.text.strip()
    if oid.lower() in ["/refresh","отмена","cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return
    if oid not in orders:
        await message.answer("❌ Заказ не найден. Проверьте номер или /refresh для отмены:"); return
    o = orders[oid]
    if o.user_id != message.from_user.id:
        await message.answer("❌ Это не ваш заказ."); return
    if o.status != "pending":
        await message.answer(f"❌ Заказ уже обработан: {o.status}"); await state.clear(); return
    await state.update_data(order_id=oid)
    await message.answer(f"✅ Заказ {oid} найден. Теперь отправьте скриншот оплаты (фото).")

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    oid = data.get('order_id')
    if not oid or oid not in orders:
        await message.answer("❌ Сначала введите номер заказа."); await state.clear(); return
    o = orders[oid]
    if o.user_id != message.from_user.id:
        await message.answer("❌ Это не ваш заказ."); await state.clear(); return
    if o.status != "pending":
        await message.answer(f"❌ Заказ уже обработан."); await state.clear(); return
    o.payment_proof = message.photo[-1].file_id
    save_data()
    await message.answer("✅ Скриншот получен! Ожидайте подтверждения администратора (до 24 часов).")
    card_name = cards.get(o.card_id, Card('','?','basic')).name if o.card_id in cards else o.card_id
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, o.payment_proof,
                caption=f"📤 Скриншот оплаты!\n🆔 {oid}\n👤 @{message.from_user.username}\n🎴 {card_name}\n💰 {o.price}₽",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_order_{oid}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{oid}"),
                ]]))
        except: pass
    await state.clear()


# ════════════════════════════════════════════════════════════════════════════════
# Открытие карточки в чате
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(F.text.lower().in_(["фанко","функо","fanco","funko","фанка","фанку"]))
async def open_fanco(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]: return
    user_id = message.from_user.id
    user = users.get(user_id)
    if user:
        ok, reason = check_user_access(user)
        if not ok:
            await message.reply(f"⛔ {reason}"); return
    # Для первого открытия карты проверяем подписку
    if user_id not in users:
        if not await check_subscription(user_id):
            await message.reply(f"❌ Подпишитесь на {CHANNEL_LINK}"); return
    user = get_or_create_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    can_open, remaining = can_open_card(user)
    if not can_open:
        await message.reply(
            f"⏰ <b>Подождите ещё {remaining}</b>\n\n"
            f"⚡ Скип кулдауна можно купить в магазине!"); return
    result = open_card(user)
    if not result:
        await message.reply("❌ Нет доступных карточек."); return
    card, card_id = result
    icon = get_rarity_color(card.rarity)
    disc = get_level_discount(user.level)
    disc_text = f"\n🎁 Ваша скидка: {disc}%" if disc else ""
    text = (
        f"🎴 <b>{message.from_user.first_name}, вы получили карточку!</b>\n\n"
        f"{icon} <b>{card.name}</b>\n"
        f"📊 {get_rarity_name(card.rarity)}\n"
        f"📈 Карточек: {sum(user.cards.values())}\n"
        f"🎫 Токены: {user.tokens} (+{3 if user.is_premium else 1})\n"
        f"🎮 Уровень: {user.level}{disc_text}\n\n"
        f"⏰ Следующая через {get_card_cooldown_hours(user)} ч"
    )
    fp = get_image_path(card)
    if fp and os.path.exists(fp):
        try:
            if is_video_card(card):
                await message.reply_video(FSInputFile(fp), caption=text)
            else:
                await message.reply_photo(FSInputFile(fp), caption=text)
            return
        except Exception as e:
            logger.error(f"Ошибка отправки медиа: {e}")
    await message.reply(text)


# ════════════════════════════════════════════════════════════════════════════════
# Инвентарь
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(F.text == "🎴 Инвентарь")
async def inventory_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id)
    if not user.cards:
        await message.answer("📭 <b>Инвентарь пуст!</b>\n\nНапишите <b>фанко</b> в групповом чате."); return
    user_inventory_pages[message.from_user.id] = {'current_page': 0, 'cards': list(user.cards.items())}
    await show_inventory_page(message.from_user.id, message.chat.id)

async def show_inventory_page(user_id: int, chat_id: int):
    if user_id not in user_inventory_pages: return
    data = user_inventory_pages[user_id]
    cards_list = data['cards']
    page = data['current_page']
    per_page = 10
    total_pages = (len(cards_list) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(cards_list))
    kb = InlineKeyboardBuilder()
    for cid, qty in cards_list[start:end]:
        card = cards.get(cid)
        if card:
            icon = get_rarity_color(card.rarity)
            vicon = "🎬 " if is_video_card(card) else ""
            kb.add(InlineKeyboardButton(text=f"{icon} {vicon}{card.name} (x{qty})",
                                        callback_data=f"view_card_{cid}"))
    kb.adjust(1)
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"inventory_page_{page-1}"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"inventory_page_{page+1}"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu"))
    await bot.send_message(chat_id,
        f"🎴 <b>Инвентарь</b>\n\nСтраница {page+1}/{total_pages}\n"
        f"📚 Карточек: {sum(q for _,q in cards_list)} | ⭐ Уникальных: {len(cards_list)}",
        reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("inventory_page_"))
async def inventory_page_handler(callback: types.CallbackQuery):
    page = int(callback.data.replace("inventory_page_", ""))
    uid = callback.from_user.id
    if uid in user_inventory_pages:
        user_inventory_pages[uid]['current_page'] = page
        await callback.message.delete()
        await show_inventory_page(uid, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_card_"))
async def view_card_handler(callback: types.CallbackQuery):
    cid = callback.data.replace("view_card_", "")
    card = cards.get(cid)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    qty = user.cards.get(cid, 0)
    text = (f"{get_rarity_color(card.rarity)} <b>{card.name}</b>\n\n"
            f"📊 {get_rarity_name(card.rarity)}\n📈 {qty} шт.\n🆔 {cid}")
    fp = get_image_path(card)
    if fp and os.path.exists(fp):
        try:
            if is_video_card(card): await callback.message.answer_video(FSInputFile(fp), caption=text)
            else: await callback.message.answer_photo(FSInputFile(fp), caption=text)
        except: await callback.message.answer(text)
    else:
        await callback.message.answer(text)
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Колесо фортуны (большое) — UI
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(F.text == "🎡 Колесо фортуны")
async def wheel_menu_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    global current_wheel
    user = get_or_create_user(message.from_user.id)
    if datetime.now() >= current_wheel.end_time:
        await draw_wheel_winners()
    time_left = current_wheel.end_time - datetime.now()
    days, hours = time_left.days, time_left.seconds // 3600
    minutes = (time_left.seconds % 3600) // 60

    # Ежедневное колесо
    today = datetime.now().date().isoformat()
    daily_available = (user.daily_wheel_claimed != today)

    kb = InlineKeyboardBuilder()
    if daily_available:
        kb.add(InlineKeyboardButton(text="🎰 Ежедневный бесплатный спин!", callback_data="daily_wheel_spin"))
    else:
        kb.add(InlineKeyboardButton(text="🎰 Спин использован (завтра)", callback_data="daily_wheel_info"))
    kb.add(InlineKeyboardButton(text="🎫 Купить билеты (1🎫 за билет)", callback_data="wheel_buy_start"))
    kb.add(InlineKeyboardButton(text="👥 Участники", callback_data="wheel_participants"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(1)

    my_tickets = current_wheel.participants.get(user.user_id, 0)
    await message.answer(
        f"🎡 <b>Колесо фортуны</b>\n\n"
        f"🕐 Розыгрыш через: {days}д {hours}ч {minutes}м\n"
        f"🎫 Всего билетов: {current_wheel.get_total_tickets()}\n"
        f"👥 Участников: {current_wheel.get_participants_count()}\n"
        f"🎟 Ваших билетов: {my_tickets}\n\n"
        f"<b>Призы большого колеса:</b>\n"
        f"🟣 Виниловая (1%) | 🟡 Лег. (4%) | 🔵 Крутая (10%) | ⚡ Скипы (60%) | 🎫 Токены (25%)\n\n"
        f"<b>Ежедневный спин (бесплатно):</b>\n"
        f"Малые призы: токены, скипы, бесплатный билет, базовая карточка",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data == "daily_wheel_spin")
async def daily_wheel_spin_handler(callback: types.CallbackQuery):
    await callback.answer()  # Отвечаем СРАЗУ — иначе "query is too old"
    user = get_or_create_user(callback.from_user.id)
    today = datetime.now().date().isoformat()
    if user.daily_wheel_claimed == today:
        await callback.message.answer("❌ Вы уже крутили сегодня! Приходите завтра 🌙")
        return
    prize = DailyWheel.spin(user.is_premium)
    user.daily_wheel_claimed = today
    try:
        if prize["type"] == "tokens":
            user.tokens += prize["amount"]
            add_event_score(user.user_id, "collect_tokens", prize["amount"])
            prize_text = f"+{prize['amount']}🎫"
        elif prize["type"] == "skip_card":
            user.skip_card_cooldown_available = True
            prize_text = "⚡ Скип кулдауна карточки"
        elif prize["type"] == "skip_trade":
            user.skip_trade_cooldown_available = True
            prize_text = "⚡ Скип кулдауна обменов"
        elif prize["type"] == "free_ticket":
            current_wheel.add_tickets(user.user_id, prize["amount"])
            prize_text = f"🎟 +{prize['amount']} билет(а) большого колеса"
        elif prize["type"] == "basic_card":
            basic_cards_list = [cid for cid, c in cards.items() if c.rarity == "basic"]
            if basic_cards_list:
                won_cid = random.choice(basic_cards_list)
                user.cards[won_cid] = user.cards.get(won_cid, 0) + 1
                prize_text = f"⚪ {cards[won_cid].name}"
            else:
                user.tokens += 5; prize_text = "+5🎫"
        else:
            user.tokens += prize["amount"]; prize_text = f"+{prize['amount']}🎫"
    except Exception as e:
        logger.error(f"daily_wheel_spin prize error: {e}")
        user.tokens += 3; prize_text = "+3🎫"
    save_data()
    prem_note = "\n<i>✨ x2 токены за Премиум!</i>" if user.is_premium and prize["type"] == "tokens" else ""
    await callback.message.answer(
        f"🎰 <b>Ежедневный спин!</b>\n\n"
        f"🎁 {prize['name']}: <b>{prize_text}</b>{prem_note}\n\n"
        f"💰 Баланс токенов: {user.tokens}🎫\n\n"
        f"<i>Следующий бесплатный спин — завтра</i>"
    )
@dp.callback_query(lambda c: c.data == "daily_wheel_info")
async def daily_wheel_info_handler(callback: types.CallbackQuery):
    await callback.answer("Следующий бесплатный спин доступен завтра!", show_alert=True)

@dp.callback_query(lambda c: c.data == "wheel_buy_start")
async def wheel_buy_start_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🎫 За токены", callback_data="wheel_buy_tokens"))
    kb.add(InlineKeyboardButton(text="⭐ За звёзды (1 билет = 1 звезда)", callback_data="wheel_buy_stars_select"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(1)
    await callback.message.answer(
        f"🎫 <b>Покупка билетов колеса фортуны</b>\n\n"
        f"💰 Ваш баланс: {user.tokens}🎫\n"
        f"🎟 Ваших билетов: {current_wheel.participants.get(user.user_id, 0)}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data == "wheel_buy_tokens")
async def wheel_buy_tokens_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    await callback.message.answer(
        f"🎫 <b>Покупка билетов за токены</b>\n\nВаш баланс: {user.tokens}🎫\n1 билет = 1🎫\n\nВведите количество билетов:")
    await state.set_state(WheelBuyState.entering_ticket_amount)

@dp.callback_query(lambda c: c.data == "wheel_buy_stars_select")
async def wheel_buy_stars_select_handler(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    for count in [1, 5, 10, 25, 50]:
        kb.add(InlineKeyboardButton(
            text=f"{count} билет(а) за {count}⭐",
            callback_data=f"wheel_buy_stars_{count}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="wheel_buy_start"))
    kb.adjust(2)
    await callback.message.answer(
        "⭐ <b>Покупка билетов за Telegram Stars</b>\n\n"
        "1 билет = 1 звезда\nВыберите количество:",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("wheel_buy_stars_"))
async def wheel_buy_stars_handler(callback: types.CallbackQuery):
    await callback.answer()
    try:
        count = int(callback.data.replace("wheel_buy_stars_", ""))
    except:
        return
    user = get_or_create_user(callback.from_user.id)
    payload = f"wheel_tickets:{count}:{user.user_id}:{int(datetime.now().timestamp())}"
    prices = [LabeledPrice(label=f"{count} билет(а) для Колеса фортуны", amount=count)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Билеты для Колеса фортуны ({count} шт.)",
            description=f"{count} билет(а) = {count}⭐. Больше билетов — выше шанс выигрыша!",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
        )
    except Exception as e:
        logger.error(f"Ошибка создания инвойса для колеса: {e}")
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте ещё раз.")

@dp.message(WheelBuyState.entering_ticket_amount)
async def wheel_buy_amount_handler(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id)
    try:
        amount = int(message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await message.answer("❌ Введите положительное число."); return
    if user.tokens < amount:
        await message.answer(f"❌ Недостаточно токенов! Нужно {amount}🎫, у вас {user.tokens}🎫"); return
    user.tokens -= amount
    current_wheel.add_tickets(user.user_id, amount)
    save_data()
    await message.answer(
        f"✅ <b>Билеты куплены!</b>\n\nКуплено: {amount}🎫\nОстаток: {user.tokens}🎫\n"
        f"Ваших билетов в колесе: {current_wheel.participants.get(user.user_id, 0)}")
    await state.clear()

@dp.callback_query(lambda c: c.data == "wheel_participants")
async def wheel_participants_handler(callback: types.CallbackQuery):
    if not current_wheel.participants:
        await callback.answer("Пока нет участников", show_alert=True); return
    sorted_p = sorted(current_wheel.participants.items(), key=lambda x: x[1], reverse=True)
    r = "👥 <b>Участники:</b>\n\n"
    for i, (uid, tickets) in enumerate(sorted_p[:20], 1):
        u = users.get(uid)
        name = f"@{u.username}" if u and u.username else f"ID:{uid}"
        r += f"{i}. {name} — {tickets} билетов\n"
    await callback.answer()
    await callback.message.answer(r)


# ════════════════════════════════════════════════════════════════════════════════
# Секретный магазин
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(F.text == "🤫МАГАЗИН🤫")
async def secret_shop_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id)
    if not hasattr(user, 'secret_shop_expires') or not user.secret_shop_expires:
        await message.answer("❌ У вас нет доступа к секретному магазину."); return
    if datetime.fromisoformat(user.secret_shop_expires) <= datetime.now():
        await message.answer("⏰ Время секретного магазина истекло.", reply_markup=get_main_menu(user)); return

    time_left = datetime.fromisoformat(user.secret_shop_expires) - datetime.now()
    minutes_left = int(time_left.total_seconds() // 60)

    regular_cards = [(cid, item) for cid, item in shop_items.items() if not cid.startswith('skip_')]
    if not regular_cards and not exclusive_cards:
        await message.answer("🤫 <b>Секретный магазин пуст</b>\n\nПопробуйте позже."); return

    kb = InlineKeyboardBuilder()
    # Показываем карточки из обычного магазина и эксклюзивов со скидкой 30-40%
    items_shown = []
    for cid, item in regular_cards[:5]:
        card = cards.get(cid)
        if not card: continue
        discount_pct = random.randint(SECRET_SHOP_DISCOUNT_MIN, SECRET_SHOP_DISCOUNT_MAX)
        secret_price = max(int(item.price * (100 - discount_pct) / 100), 1)
        items_shown.append((cid, card, secret_price, discount_pct))
        kb.add(InlineKeyboardButton(
            text=f"{get_rarity_color(card.rarity)} {card.name} — {secret_price}₽ (-{discount_pct}%)",
            callback_data=f"secret_buy_{cid}_{secret_price}"
        ))
    for cid, exc in list(exclusive_cards.items())[:3]:
        if not exc.can_purchase(): continue
        card = cards.get(cid)
        if not card: continue
        discount_pct = random.randint(SECRET_SHOP_DISCOUNT_MIN, SECRET_SHOP_DISCOUNT_MAX)
        secret_price = max(int(exc.price * (100 - discount_pct) / 100), 1)
        kb.add(InlineKeyboardButton(
            text=f"🎪 {card.name} — {secret_price}₽ (-{discount_pct}%)",
            callback_data=f"secret_buy_excl_{cid}_{secret_price}"
        ))
    kb.adjust(1)
    await message.answer(
        f"🤫 <b>СЕКРЕТНЫЙ МАГАЗИН</b>\n\n"
        f"Эксклюзивные скидки только для вас!\n"
        f"⏰ Осталось: {minutes_left} минут\n\n"
        f"Все цены снижены на {SECRET_SHOP_DISCOUNT_MIN}–{SECRET_SHOP_DISCOUNT_MAX}%",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("secret_buy_excl_"))
async def secret_buy_excl_handler(callback: types.CallbackQuery):
    parts = callback.data.replace("secret_buy_excl_", "").rsplit("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка", show_alert=True); return
    cid, price_str = parts
    user = get_or_create_user(callback.from_user.id)
    if not user.secret_shop_expires or datetime.fromisoformat(user.secret_shop_expires) <= datetime.now():
        await callback.answer("⏰ Время секретного магазина истекло!", show_alert=True); return
    exc = exclusive_cards.get(cid)
    card = cards.get(cid)
    if not exc or not card or not exc.can_purchase():
        await callback.answer("❌ Карточка недоступна!", show_alert=True); return
    price = int(price_str)
    order_id = f"secret_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, cid, price)
    orders[order_id] = order
    save_data()
    await callback.message.answer(
        f"✅ Заказ создан!\n🎁 {card.name}\n💰 {price}₽ (секретная цена!)\n🆔 <code>{order_id}</code>\n\n"
        f"Оплатите и отправьте скриншот через /payment"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("secret_buy_"))
async def secret_buy_handler(callback: types.CallbackQuery):
    parts = callback.data.replace("secret_buy_", "").rsplit("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка", show_alert=True); return
    cid, price_str = parts
    user = get_or_create_user(callback.from_user.id)
    if not user.secret_shop_expires or datetime.fromisoformat(user.secret_shop_expires) <= datetime.now():
        await callback.answer("⏰ Время истекло!", show_alert=True); return
    card = cards.get(cid)
    if not card:
        await callback.answer("❌ Карточка не найдена!", show_alert=True); return
    price = int(price_str)
    order_id = f"secret_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, cid, price)
    orders[order_id] = order
    save_data()
    await callback.message.answer(
        f"✅ Заказ создан!\n🎁 {card.name}\n💰 {price}₽ (секретная цена!)\n🆔 <code>{order_id}</code>\n\n"
        f"Оплатите и отправьте скриншот через /payment"
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Топы
# ════════════════════════════════════════════════════════════════════════════════
@dp.message(F.text == "🏆 Топ игроков")
async def top_players_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📊 По % коллекции", callback_data="top_collection_percentage"))
    kb.add(InlineKeyboardButton(text="⭐ По уникальным картам", callback_data="top_unique_cards"))
    kb.add(InlineKeyboardButton(text="🎴 По общему кол-ву", callback_data="top_total_cards"))
    kb.add(InlineKeyboardButton(text="💰 Топ покупателей", callback_data="top_spenders_btn"))
    kb.add(InlineKeyboardButton(text="🎉 Текущий ивент", callback_data="top_event"))
    kb.add(InlineKeyboardButton(text="🏆 Реф. конкурс", callback_data="referral_contest"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(2)
    active = sum(1 for u in users.values() if not u.is_banned and not u.is_frozen)
    event_name = ""
    if current_weekly_event:
        from events import EVENT_NAMES
        event_name = f"\n🎉 Ивент: {EVENT_NAMES.get(current_weekly_event.event_type, '?')}"
    await message.answer(
        f"🏆 <b>Топ игроков</b>\n\nИгроков: {active} | Карточек: {len(cards)}{event_name}",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data == "top_event")
async def top_event_handler(callback: types.CallbackQuery):
    if not current_weekly_event:
        await callback.answer("Нет активного ивента", show_alert=True); return
    from events import EVENT_NAMES
    top = current_weekly_event.get_top(10)
    end = datetime.fromisoformat(current_weekly_event.end_time)
    days_left = max(0, (end - datetime.now()).days)
    r = f"🎉 <b>{EVENT_NAMES.get(current_weekly_event.event_type, 'Ивент')}</b>\n⏰ Осталось: {days_left} дней\n\n"
    for i, (uid, score) in enumerate(top, 1):
        u = users.get(uid)
        name = f"@{u.username}" if u else f"ID:{uid}"
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} {name}: {score}\n"
    user = get_or_create_user(callback.from_user.id)
    my_score = current_weekly_event.scores.get(user.user_id, 0)
    r += f"\n👤 Ваш счёт: {my_score}"
    await callback.answer()
    await callback.message.answer(r)

@dp.callback_query(lambda c: c.data == "top_spenders_btn")
async def top_spenders_btn_handler(callback: types.CallbackQuery):
    top = get_top_spenders(30, 5)
    r = "💰 <b>Топ покупателей (месяц)</b>\n\n"
    for i, d in enumerate(top, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} @{d['user'].username}: {d['total_spent']}₽\n"
    await callback.answer()
    await callback.message.answer(r)

@dp.callback_query(lambda c: c.data == "top_collection_percentage")
async def top_collection_percentage_handler(callback: types.CallbackQuery):
    total_cards = len(cards)
    stats = sorted([(u, len(u.cards)/total_cards*100 if total_cards else 0) for u in users.values()
                    if not u.is_banned], key=lambda x: x[1], reverse=True)[:10]
    r = "📊 <b>По % коллекции</b>\n\n"
    for i, (u, pct) in enumerate(stats, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} @{u.username}: {pct:.1f}%\n"
    await callback.answer()
    await callback.answer()
    await callback.answer()
    await callback.message.answer(r); await callback.answer()

@dp.callback_query(lambda c: c.data == "top_unique_cards")
async def top_unique_cards_handler(callback: types.CallbackQuery):
    stats = sorted([u for u in users.values() if not u.is_banned],
                   key=lambda u: len(u.cards), reverse=True)[:10]
    r = "⭐ <b>По уникальным карточкам</b>\n\n"
    for i, u in enumerate(stats, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} @{u.username}: {len(u.cards)}\n"
    await callback.answer()
    await callback.answer()
    await callback.answer()
    await callback.message.answer(r); await callback.answer()

@dp.callback_query(lambda c: c.data == "top_total_cards")
async def top_total_cards_handler(callback: types.CallbackQuery):
    stats = sorted([u for u in users.values() if not u.is_banned],
                   key=lambda u: sum(u.cards.values()), reverse=True)[:10]
    r = "🎴 <b>По общему кол-ву</b>\n\n"
    for i, u in enumerate(stats, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        r += f"{medal} @{u.username}: {sum(u.cards.values())}\n"
    await callback.answer()
    await callback.answer()
    await callback.answer()
    await callback.message.answer(r); await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Back to menu
# ════════════════════════════════════════════════════════════════════════════════
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id, callback.from_user.username or "")
    await callback.message.answer("🏠 <b>Главное меню</b>", reply_markup=get_main_menu(user))

@dp.message(F.text == "❓ Помощь")
async def help_menu(message: types.Message):
    await help_command(message)


# ════════════════════════════════════════════════════════════════════════════════
# Периодические задачи
# ════════════════════════════════════════════════════════════════════════════════
async def periodic_tasks():
    tick = 0
    while True:
        try:
            global current_wheel, current_weekly_event, current_referral_contest
            # Большое колесо
            if datetime.now() >= current_wheel.end_time:
                await draw_wheel_winners()
            # Эксклюзивы
            for exc in exclusive_cards.values():
                if exc.end_date and datetime.fromisoformat(exc.end_date) < datetime.now():
                    exc.is_active = False
            # Флэш-цены
            restore_flash_prices()
            # Каждые 30 мин — шанс применить флэш-скидку
            if tick % 30 == 0:
                if random.random() < 0.3:
                    apply_flash_discount_to_shop()
            # Каждый час — секретный магазин + ивенты
            if tick % 60 == 0:
                await maybe_send_secret_shop_notification()
                if current_weekly_event:
                    from events import check_and_rotate_weekly_event, setup_events, new_weekly_event
                    if datetime.now() >= datetime.fromisoformat(current_weekly_event.end_time):
                        await check_and_rotate_weekly_event()
                if current_referral_contest:
                    from events import check_and_rotate_referral_contest
                    if datetime.now() >= datetime.fromisoformat(current_referral_contest.end_time):
                        await check_and_rotate_referral_contest()
            if tick % 5 == 0:  # Сохраняем каждые 5 минут
                save_data()
        except Exception as e:
            logger.error(f"Ошибка в periodic_tasks: {e}")
            import traceback; traceback.print_exc()
        await asyncio.sleep(60)
        tick += 1


# ════════════════════════════════════════════════════════════════════════════════
# main()
# ════════════════════════════════════════════════════════════════════════════════
async def main():
    load_data()

    # ── Подключение роутеров ──────────────────────────────────────────────────
    from game_handlers import game_router, setup_game_handlers
    from craft_handlers import craft_router, setup_craft_handlers
    from profile_handlers import profile_router, setup_profile_handlers
    from shop_handlers import shop_router, setup_shop_handlers
    from trade_route_handlers import trade_router, setup_trade_handlers
    from admin_handlers import admin_router, setup_admin_handlers
    import events as events_module

    # Подключаем к events module глобальные ссылки
    events_module.bot = bot
    events_module.users = users
    events_module.cards = cards
    events_module.save_data = save_data
    events_module.add_premium = add_premium
    events_module.current_weekly_event = current_weekly_event
    events_module.current_referral_contest = current_referral_contest

    dp.include_router(game_router)
    dp.include_router(craft_router)
    dp.include_router(profile_router)
    dp.include_router(shop_router)
    dp.include_router(trade_router)
    dp.include_router(admin_router)

    setup_game_handlers(
        bot, users, cards, active_game_challenges, save_data,
        get_or_create_user, get_user_by_username, is_video_card,
        get_rarity_color, get_rarity_name, logger, add_event_score
    )
    setup_craft_handlers(
        bot, users, cards, save_data, get_or_create_user,
        get_rarity_color, get_rarity_name, check_access_before_handle
    )
    setup_profile_handlers(
        bot, users, cards, orders, save_data,
        get_or_create_user, check_access_before_handle, check_subscription,
        get_level_discount, get_price_with_discount, get_token_price,
        get_rarity_color, get_rarity_name,
        can_open_card, can_trade, get_card_cooldown_hours, get_trade_cooldown_hours,
        get_cooldown_by_level, get_level_progress_bar, calculate_level_exp,
        get_personal_recommendations, get_main_menu, show_payment_methods
    )
    setup_shop_handlers(
        bot, users, cards, shop_items, orders, exclusive_cards,
        save_data, get_or_create_user, check_access_before_handle, check_subscription,
        get_level_discount, get_price_with_discount, get_token_price,
        get_rarity_color, get_rarity_name,
        update_shop, update_user_interaction, show_payment_methods, create_order
    )
    setup_trade_handlers(
        bot, users, cards, trades, save_data,
        get_or_create_user, get_user_by_username,
        check_access_before_handle, check_subscription,
        can_trade, add_experience, get_rarity_color, is_video_card
    )
    setup_admin_handlers(
        bot, users, cards, card_pool, trades,
        shop_items, orders, exclusive_cards, promo_manager, current_wheel,
        save_data, load_data, get_or_create_user, get_user_by_username,
        update_user_interaction,
        add_premium, add_reduced_cd, add_reduced_trade_cd, add_cooldown, update_card_pool,
        get_rarity_color, get_rarity_name, is_video_card, get_image_path, get_video_path,
        ban_user, confirm_order, reject_order, send_order_notification, get_top_spenders,
        DATA_DIR, IMAGES_DIR, VIDEOS_DIR, USERS_FILE, Card
    )

    logger.info("=" * 50)
    logger.info(f"🚀 Бот запускается...")
    logger.info(f"👥 Пользователей: {len(users)}")
    logger.info(f"🎴 Карточек: {len(cards)}")
    logger.info(f"📦 Заказов: {len(orders)}")
    logger.info("=" * 50)

    asyncio.create_task(periodic_tasks())
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
        save_data()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        save_data()
