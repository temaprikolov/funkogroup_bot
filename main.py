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
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8280702499:AAEScyLnr4z5wW84vOElGrTBmDy3fgOFRck"
ADMIN_IDS = [8033943956, 7571242177]
PREMIUM_COST = 299
REDUCED_CD_COST = 400
REDUCED_TRADE_CD_COST = 150

SHOP_PRICES = {
    "basic": 99,
    "cool": 199,
    "legendary": 249,
    "vinyl figure": 349
}

CHANNEL_ID = -1003750249832
CHANNEL_LINK = "https://t.me/funkopopcards"
CHANNEL_USERNAME = "@funkopopcards"

INACTIVITY_DAYS = 7
INACTIVITY_CHECK_INTERVAL = 3600

MESSAGE_LIMIT = 5
TIME_WINDOW = 1
user_message_times = defaultdict(list)

LEVEL_SETTINGS = {
    'enabled': True,
    'base_exp_per_level': 100,
    'exp_multiplier': 1.5,
    
    'level_rewards': {
        5: "unique_card_lvl5",
        10: "unique_card_lvl10", 
        20: "title_collector",
        30: "unique_card_lvl30",
        50: "title_legend"
    },
    
    'exp_actions': {
        'open_card': 10,
        'purchase_card': 50,
        'trade_complete': 20,
        'daily_login': 5,
        'referral': 50,
        'welcome_bonus': 100
    }
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN or BOT_TOKEN == "":
    logger.error("❌ Токен бота не настроен! Замени BOT_TOKEN на свой токен от @BotFather")
    exit(1)

logger.info(f"✅ Токен загружен")
logger.info(f"✅ Бот настроен для {len(ADMIN_IDS)} администраторов")

DATA_DIR = Path("data")
IMAGES_DIR = DATA_DIR / "images"
DATA_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

bot = Bot(token=BOT_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class User:
    def __init__(self, user_id: int, username: str = "", first_name: str = ""):
        self.user_id = user_id
        self.username = username or f"user_{user_id}"
        self.first_name = first_name
        self.cards: Dict[str, int] = {}
        self.opened_packs = 0
        self.created_at = datetime.now().isoformat()
        self.last_seen = datetime.now().isoformat()
        self.last_interaction = datetime.now().isoformat()
        self.is_premium = False
        self.premium_until: Optional[str] = None
        self.has_reduced_cd = False
        self.reduced_cd_until: Optional[str] = None
        self.has_reduced_trade_cd = False
        self.reduced_trade_cd_until: Optional[str] = None
        self.last_card_time: Optional[str] = None
        self.last_trade_time: Optional[str] = None
        self.daily_bonus_claimed: Optional[str] = None
        self.last_shop_check: Optional[str] = None
        self.last_reminder_sent: Optional[str] = None
        self.is_banned = False
        self.ban_reason: Optional[str] = None
        self.banned_until: Optional[str] = None
        self.is_frozen = False
        self.frozen_until: Optional[str] = None
        self.level = 1
        self.experience = 0
        self.total_exp_earned = 0
        self.secret_total_spent = 0
        self.last_daily_exp = None
        self.referrals = []  
        self.referrer_id = None  
        self.referral_bonus_claimed = False 

class Card:
    def __init__(self, card_id: str, name: str, rarity: str, image_filename: str = ""):
        self.card_id = card_id
        self.name = name
        self.rarity = rarity
        self.image_filename = image_filename

class ShopItem:
    def __init__(self, card_id: str, price: int, expires_at: str):
        self.card_id = card_id
        self.price = price
        self.expires_at = expires_at

class Order:
    def __init__(self, order_id: str, user_id: int, card_id: str, price: int, status: str = "pending"):
        self.order_id = order_id
        self.user_id = user_id
        self.card_id = card_id
        self.price = price
        self.status = status
        self.created_at = datetime.now().isoformat()
        self.confirmed_at: Optional[str] = None
        self.admin_id: Optional[int] = None
        self.payment_proof: Optional[str] = None

class ExclusiveCard:
    def __init__(self, card_id: str, total_copies: int, price: int, end_date: Optional[str] = None):
        self.card_id = card_id
        self.total_copies = total_copies
        self.sold_copies = 0
        self.price = price
        self.end_date = end_date
        self.is_active = True
    
    def can_purchase(self) -> bool:
        if not self.is_active:
            return False
        if self.sold_copies >= self.total_copies:
            return False
        if self.end_date and datetime.fromisoformat(self.end_date) < datetime.now():
            return False
        return True
    
    def purchase_copy(self) -> bool:
        if self.can_purchase():
            self.sold_copies += 1
            if self.sold_copies >= self.total_copies:
                self.is_active = False
            return True
        return False

users: Dict[int, User] = {}
cards: Dict[str, Card] = {}
card_pool: List[str] = []
trades: Dict[str, Dict] = {}
user_inventory_pages: Dict[int, Dict] = {}
shop_items: Dict[str, ShopItem] = {}
orders: Dict[str, Order] = {}
exclusive_cards: Dict[str, ExclusiveCard] = {}
card_popularity: Dict[str, Dict] = {}

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"
CARDS_FILE = DATA_DIR / "cards.json"
TRADES_FILE = DATA_DIR / "trades.json"
SHOP_FILE = DATA_DIR / "shop.json"
ORDERS_FILE = DATA_DIR / "orders.json"
LEVELS_FILE = DATA_DIR / "levels.json"
EXCLUSIVES_FILE = DATA_DIR / "exclusives.json"
POPULARITY_FILE = DATA_DIR / "popularity.json"

async def check_access_before_handle(message_or_callback, user_id: int) -> bool:
    user = get_or_create_user(user_id)
    
    has_access, reason = check_user_access(user)
    if not has_access:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(f"⛔ <b>Доступ запрещен!</b>\n\n{reason}")
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(f"⛔ Доступ запрещен: {reason}", show_alert=True)
        return False
    
    if isinstance(message_or_callback, types.Message):
        if check_spam(user_id) and user_id not in ADMIN_IDS:
            await message_or_callback.answer("⚠️ <b>Не спамь!</b> Слишком много сообщений за короткое время.")
            return False
    
    return True

def check_spam(user_id: int) -> bool:
    current_time = datetime.now().timestamp()
    
    user_message_times[user_id] = [
        time for time in user_message_times[user_id]
        if current_time - time < TIME_WINDOW
    ]
    
    if len(user_message_times[user_id]) >= MESSAGE_LIMIT:
        return True
    
    user_message_times[user_id].append(current_time)
    return False

async def send_order_notification(order_id: str, user_id: int, card_name: str, price: int) -> bool:
    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>Ваш заказ подтвержден!</b>\n\n"
            f"🆔 Заказ: {order_id}\n"
            f"🎴 Карточка: <b>{card_name}</b>\n"
            f"💰 Сумма: {price}₽\n\n"
            f"✅ Карточка добавлена в ваш инвентарь!\n"
            f"Проверьте инвентарь чтобы увидеть её."
        )
        logger.info(f"Уведомление о заказе {order_id} отправлено пользователю {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        return False

async def show_payment_methods(callback: types.CallbackQuery, product_type: str, product_id: str, price: int, description: str = ""):
    keyboard = InlineKeyboardBuilder()
    
    keyboard.add(InlineKeyboardButton(
        text="🏦 Перевод на Т-Банк",
        callback_data=f"payment_method:transfer:{product_type}:{product_id}:{price}"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text="🔗 Оплата по ссылке",
        callback_data=f"payment_method:link:{product_type}:{product_id}:{price}"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text="👨‍💼 Через администратора",
        callback_data=f"payment_method:admin:{product_type}:{product_id}:{price}"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_menu"
    ))
    keyboard.adjust(1)
    
    await callback.message.answer(
        f"💵 <b>Выберите способ оплата</b>\n\n"
        f"🎁 <b>Товар:</b> {description}\n"
        f"💰 <b>Сумма:</b> {price}₽\n\n"
        f"<b>Доступные способы оплаты:</b>\n"
        f"1. 🏦 <b>Перевод на Т-Банк</b> - получите реквизиты карты\n"
        f"2. 🔗 <b>Оплата по ссылке</b> - перейдите по готовой ссылке\n"
        f"3. 👨‍💼 <b>Через администратора</b> - для индивидуальной оплаты\n\n"
        f"📸 <b>После оплаты:</b>\n"
        f"Используйте команду /payment и введите номер заказа\n"
        f"Затем отправьте скриншот оплаты.",
        reply_markup=keyboard.as_markup()
    )
    
async def check_subscription(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )
        status = chat_member.status
        return status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

def get_subscription_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="📢 Подписаться на канал", 
        url=CHANNEL_LINK
    ))
    keyboard.add(InlineKeyboardButton(
        text="✅ Я подписался", 
        callback_data="check_subscription"
    ))
    return keyboard.as_markup()

def is_user_banned(user: User) -> Tuple[bool, Optional[str]]:
    if not user.is_banned:
        return False, None
    
    if user.banned_until:
        banned_until = datetime.fromisoformat(user.banned_until)
        if banned_until <= datetime.now():
            user.is_banned = False
            user.ban_reason = None
            user.banned_until = None
            save_data()
            return False, None
        
        time_left = banned_until - datetime.now()
        days = time_left.days
        hours = time_left.seconds // 3600
        return True, f"Забанен до {banned_until.strftime('%d.%m.%Y %H:%M')} ({days}д {hours}ч осталось). Причина: {user.ban_reason}"
    
    return True, f"Забанен навсегда. Причина: {user.ban_reason}"

def is_user_frozen(user: User) -> Tuple[bool, Optional[str]]:
    if not user.is_frozen:
        return False, None
    
    if user.frozen_until:
        frozen_until = datetime.fromisoformat(user.frozen_until)
        if frozen_until <= datetime.now():
            user.is_frozen = False
            user.frozen_until = None
            save_data()
            return False, None
        
        time_left = frozen_until - datetime.now()
        days = time_left.days
        hours = time_left.seconds // 3600
        return True, f"Аккаунт заморожен до {frozen_until.strftime('%d.%m.%Y %H:%M')} ({days}д {hours}ч осталось)"
    
    return True, "Аккаунт заморожен"

def check_user_access(user: User) -> Tuple[bool, Optional[str]]:
    is_banned, ban_reason = is_user_banned(user)
    if is_banned:
        return False, ban_reason
    
    is_frozen, freeze_reason = is_user_frozen(user)
    if is_frozen:
        return False, freeze_reason
    
    return True, None

def ban_user(user: User, reason: str = "Нарушение правил", days: int = 0):
    user.is_banned = True
    user.ban_reason = reason
    
    if days > 0:
        banned_until = datetime.now() + timedelta(days=days)
        user.banned_until = banned_until.isoformat()
    else:
        user.banned_until = None
    
    save_data()
    return True

async def check_inactive_users():
    logger.info("🔍 Проверка неактивных пользователей...")
    
    now = datetime.now()
    reminder_count = 0
    
    for user in users.values():
        if user.is_banned or user.is_frozen:
            continue
        
        if user.last_interaction:
            last_interaction = datetime.fromisoformat(user.last_interaction)
            days_inactive = (now - last_interaction).days
            
            if days_inactive >= INACTIVITY_DAYS:
                should_send_reminder = True
                
                if user.last_reminder_sent:
                    last_reminder = datetime.fromisoformat(user.last_reminder_sent)
                    days_since_reminder = (now - last_reminder).days
                    if days_since_reminder < 7:
                        should_send_reminder = False
                
                if should_send_reminder:
                    try:
                        await send_reminder_message(user)
                        user.last_reminder_sent = now.isoformat()
                        reminder_count += 1
                        logger.info(f"📨 Отправлено напоминание пользователю {user.user_id}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания пользователю {user.user_id}: {e}")
    
    if reminder_count > 0:
        logger.info(f"✅ Отправлено {reminder_count} напоминаний неактивным пользователям")
    
    asyncio.get_event_loop().call_later(
        INACTIVITY_CHECK_INTERVAL,
        lambda: asyncio.create_task(check_inactive_users())
    )

async def send_reminder_message(user: User):
    try:
        message = (
            "👋 <b>Привет! Давно тебя не было!</b>\n\n"
            "Ты давно не заходил в бота! Пора пополнить свою коллекцию карточек!\n\n"
            "🎴 <b>Что ты можешь сделать:</b>\n"
            "• Напиши <b>фанко</b> в группе чтобы получить карточку\n"
            "• Проверь свой инвентарь\n"
            "• Посмотри новые карточки в магазине\n"
            "• Обменяйся карточками с друзьями\n\n"
            "Не упускай возможность получить редкие карточки! 🔥"
        )
        
        await bot.send_message(user.user_id, message)
    except Exception as e:
        logger.error(f"Не удалось отправить напоминание пользователю {user.user_id}: {e}")

def update_card_pool():
    global card_pool
    card_pool = []
    
    for card_id, card in cards.items():
        if card.rarity == "basic":
            weight = 10
        elif card.rarity == "cool":
            weight = 5
        elif card.rarity == "legendary":
            weight = 2
        elif card.rarity == "vinyl figure":
            weight = 1
        else:
            weight = 1
        
        card_pool.extend([card_id] * weight)
    
    logger.info(f"✅ Пул карточек обновлен: {len(card_pool)} записей")

def load_data():
    global users, cards, card_pool, trades, shop_items, orders, exclusive_cards, card_popularity
    try:
        if USERS_FILE.exists():
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
                for user_id_str, user_data in users_data.items():
                    user_id = int(user_id_str)
                    user = User(user_id, user_data.get('username', ''), user_data.get('first_name', ''))
                    user.cards = user_data.get('cards', {})
                    user.opened_packs = user_data.get('opened_packs', 0)
                    user.created_at = user_data.get('created_at', datetime.now().isoformat())
                    user.last_seen = user_data.get('last_seen', datetime.now().isoformat())
                    user.last_interaction = user_data.get('last_interaction', datetime.now().isoformat())
                    user.is_premium = user_data.get('is_premium', False)
                    user.premium_until = user_data.get('premium_until')
                    user.has_reduced_cd = user_data.get('has_reduced_cd', False)
                    user.reduced_cd_until = user_data.get('reduced_cd_until')
                    user.has_reduced_trade_cd = user_data.get('has_reduced_trade_cd', False)
                    user.reduced_trade_cd_until = user_data.get('reduced_trade_cd_until')
                    user.last_card_time = user_data.get('last_card_time')
                    user.last_trade_time = user_data.get('last_trade_time')
                    user.daily_bonus_claimed = user_data.get('daily_bonus_claimed')
                    user.last_shop_check = user_data.get('last_shop_check')
                    user.last_reminder_sent = user_data.get('last_reminder_sent')
                    user.is_banned = user_data.get('is_banned', False)
                    user.ban_reason = user_data.get('ban_reason')
                    user.banned_until = user_data.get('banned_until')
                    user.is_frozen = user_data.get('is_frozen', False)
                    user.frozen_until = user_data.get('frozen_until')
                    user.level = user_data.get('level', 1)
                    user.experience = user_data.get('experience', 0)
                    user.total_exp_earned = user_data.get('total_exp_earned', 0)
                    user.secret_total_spent = user_data.get('secret_total_spent', 0)
                    user.referrals = user_data.get('referrals', [])
                    user.referrer_id = user_data.get('referrer_id')
                    user.referral_bonus_claimed = user_data.get('referral_bonus_claimed', False)
                    users[user_id] = user
        
        if CARDS_FILE.exists():
            with open(CARDS_FILE, 'r', encoding='utf-8') as f:
                cards_data = json.load(f)
                for card_id, card_data in cards_data.items():
                    cards[card_id] = Card(
                        card_id=card_id,
                        name=card_data['name'],
                        rarity=card_data['rarity'],
                        image_filename=card_data.get('image_filename', '')
                    )
        else:
            cards["fanco1"] = Card("fanco1", "FUNKO CARD - BASIC", "basic")
            update_card_pool()
            save_data()
        
        if TRADES_FILE.exists():
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                trades = json.load(f)
        
        if SHOP_FILE.exists():
            with open(SHOP_FILE, 'r', encoding='utf-8') as f:
                shop_data = json.load(f)
                for card_id, item_data in shop_data.items():
                    shop_items[card_id] = ShopItem(
                        card_id=card_id,
                        price=item_data['price'],
                        expires_at=item_data['expires_at']
                    )
        
        if ORDERS_FILE.exists():
            with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
                orders_data = json.load(f)
                for order_id, order_data in orders_data.items():
                    order = Order(
                        order_id=order_id,
                        user_id=order_data['user_id'],
                        card_id=order_data['card_id'],
                        price=order_data['price'],
                        status=order_data['status']
                    )
                    order.created_at = order_data.get('created_at', datetime.now().isoformat())
                    order.confirmed_at = order_data.get('confirmed_at')
                    order.admin_id = order_data.get('admin_id')
                    order.payment_proof = order_data.get('payment_proof')
                    orders[order_id] = order
        
        try:
            if LEVELS_FILE.exists():
                with open(LEVELS_FILE, 'r', encoding='utf-8') as f:
                    levels_data = json.load(f)
                    for user_id_str, user_data in levels_data.items():
                        user_id = int(user_id_str)
                        if user_id in users:
                            users[user_id].level = user_data.get('level', 1)
                            users[user_id].experience = user_data.get('experience', 0)
                            users[user_id].total_exp_earned = user_data.get('total_exp_earned', 0)
                            users[user_id].secret_total_spent = user_data.get('secret_total_spent', 0)
            
            if EXCLUSIVES_FILE.exists():
                with open(EXCLUSIVES_FILE, 'r', encoding='utf-8') as f:
                    exclusives_data = json.load(f)
                    for card_id, exclusive_data in exclusives_data.items():
                        exclusive_cards[card_id] = ExclusiveCard(
                            card_id=card_id,
                            total_copies=exclusive_data['total_copies'],
                            price=exclusive_data['price'],
                            end_date=exclusive_data.get('end_date')
                        )
                        exclusive_cards[card_id].sold_copies = exclusive_data.get('sold_copies', 0)
                        exclusive_cards[card_id].is_active = exclusive_data.get('is_active', True)
            
            if POPULARITY_FILE.exists():
                with open(POPULARITY_FILE, 'r', encoding='utf-8') as f:
                    card_popularity.update(json.load(f))
            
            logger.info(f"✅ Загружены новые данные: уровни, эксклюзивы, популярность")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки новых данных: {e}")
        
        update_card_pool()
        logger.info(f"✅ Данные загружены: {len(users)} пользователей, {len(cards)} карточек, {len(orders)} заказов")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")
        cards["fanco1"] = Card("fanco1", "FUNKO CARD - BASIC", "basic")
        update_card_pool()
        save_data()

def save_data():
    users_data = {}
    for user_id, user in users.items():
        users_data[str(user_id)] = {
            'username': user.username,
            'first_name': user.first_name,
            'cards': user.cards,
            'opened_packs': user.opened_packs,
            'created_at': user.created_at,
            'last_seen': user.last_seen,
            'last_interaction': user.last_interaction,
            'is_premium': user.is_premium,
            'premium_until': user.premium_until,
            'has_reduced_cd': user.has_reduced_cd,
            'reduced_cd_until': user.reduced_cd_until,
            'has_reduced_trade_cd': user.has_reduced_trade_cd,
            'reduced_trade_cd_until': user.reduced_trade_cd_until,
            'last_card_time': user.last_card_time,
            'last_trade_time': user.last_trade_time,
            'daily_bonus_claimed': user.daily_bonus_claimed,
            'last_shop_check': user.last_shop_check,
            'last_reminder_sent': user.last_reminder_sent,
            'is_banned': user.is_banned,
            'ban_reason': user.ban_reason,
            'banned_until': user.banned_until,
            'is_frozen': user.is_frozen,
            'frozen_until': user.frozen_until,
            'level': user.level,
            'experience': user.experience,
            'total_exp_earned': user.total_exp_earned,
            'secret_total_spent': user.secret_total_spent,
            'referrals': user.referrals,
            'referrer_id': user.referrer_id,
            'referral_bonus_claimed': user.referral_bonus_claimed
        }
    
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)
    
    cards_data = {}
    for card_id, card in cards.items():
        cards_data[card_id] = {
            'name': card.name,
            'rarity': card.rarity,
            'image_filename': card.image_filename
        }
    
    with open(CARDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(cards_data, f, ensure_ascii=False, indent=2)
    
    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)
    
    shop_data = {}
    for card_id, item in shop_items.items():
        shop_data[card_id] = {
            'price': item.price,
            'expires_at': item.expires_at
        }
    
    with open(SHOP_FILE, 'w', encoding='utf-8') as f:
        json.dump(shop_data, f, ensure_ascii=False, indent=2)
    
    orders_data = {}
    for order_id, order in orders.items():
        orders_data[order_id] = {
            'user_id': order.user_id,
            'card_id': order.card_id,
            'price': order.price,
            'status': order.status,
            'created_at': order.created_at,
            'confirmed_at': order.confirmed_at,
            'admin_id': order.admin_id,
            'payment_proof': order.payment_proof
        }
    
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders_data, f, ensure_ascii=False, indent=2)
    
    try:
        levels_data = {}
        for user_id, user in users.items():
            levels_data[str(user_id)] = {
                'level': user.level,
                'experience': user.experience,
                'total_exp_earned': user.total_exp_earned,
                'secret_total_spent': user.secret_total_spent
            }
        
        with open(LEVELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(levels_data, f, ensure_ascii=False, indent=2)
        
        exclusives_data = {}
        for card_id, exclusive in exclusive_cards.items():
            exclusives_data[card_id] = {
                'total_copies': exclusive.total_copies,
                'sold_copies': exclusive.sold_copies,
                'price': exclusive.price,
                'end_date': exclusive.end_date,
                'is_active': exclusive.is_active
            }
        
        with open(EXCLUSIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump(exclusives_data, f, ensure_ascii=False, indent=2)
        
        with open(POPULARITY_FILE, 'w', encoding='utf-8') as f:
            json.dump(card_popularity, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Новые данные сохранены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения новых данных: {e}")
    
    logger.info(f"✅ Данные сохранены: {len(users)} пользователей, {len(cards)} карточек, {len(orders)} заказов")

def update_user_interaction(user: User):
    user.last_seen = datetime.now().isoformat()
    user.last_interaction = datetime.now().isoformat()

def get_user_by_username(username: str) -> Optional[User]:
    if not username:
        return None
    
    username = username.lstrip('@').lower()
    for user in users.values():
        if user.username.lower() == username:
            return user
    return None

async def send_referral_bonus(user_id: int, referral_count: int, card_id: str):
    """Отправляет уведомление о бонусе за приглашение"""
    try:
        user = users.get(user_id)
        if not user:
            return
        
        card = cards.get(card_id)
        card_name = card.name if card else "редкая карточка"
        
        await bot.send_message(
            user_id,
            f"🎉 <b>Поздравляем! Вы пригласили {referral_count} друзей!</b>\n\n"
            f"🎁 <b>Ваш бонус:</b> {card_name}\n"
            f"👥 <b>Всего приглашено:</b> {referral_count} человек\n"
            f"✨ <b>Получено опыта:</b> {referral_count * 50} XP\n\n"
            f"Продолжайте приглашать друзей - за каждых 3 приглашенных вы получаете карточку!\n\n"
            f"📢 Ваша ссылка для приглашений:\n"
            f"<code>https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}</code>"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о бонусе: {e}")

async def send_new_referral_notification(user_id: int, new_referral_id: int):
    """Уведомляет пользователя о новом реферале"""
    try:
        user = users.get(user_id)
        new_user = users.get(new_referral_id)
        
        if not user or not new_user:
            return
        
        total_referrals = len(user.referrals)
        next_bonus_at = 3 - (total_referrals % 3) if total_referrals % 3 != 0 else 3
        
        await bot.send_message(
            user_id,
            f"🎉 <b>Новый друг присоединился по вашей ссылке!</b>\n\n"
            f"👤 <b>Новый игрок:</b> @{new_user.username or 'без username'}\n"
            f"✨ <b>Вы получили:</b> +50 XP\n"
            f"👥 <b>Всего приглашено:</b> {total_referrals} человек\n"
            f"🎯 <b>До следующей карточки:</b> {next_bonus_at} приглашенных\n\n"
            f"Продолжайте приглашать друзей - каждый новый игрок приближает вас к следующей награде!"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о новом реферале: {e}")

def get_or_create_user(user_id: int, username: str = "", first_name: str = "", referrer_id: int = None) -> User:
    if user_id not in users:
        users[user_id] = User(user_id, username, first_name)
        
        # Реферальная система: если есть referrer_id и это существующий пользователь
        if referrer_id and referrer_id in users and referrer_id != user_id:
            users[referrer_id].referrals.append(user_id)
            users[user_id].referrer_id = referrer_id
            
            # Дарим опыт тому, кто пригласил
            add_experience(users[referrer_id], 'referral', 50)
            
            # Дарим опыт новичку
            add_experience(users[user_id], 'welcome_bonus', 100)

            asyncio.create_task(send_new_referral_notification(referrer_id, user_id))
            
            # За каждых 3 приглашенных - карточка в подарок
            referral_count = len(users[referrer_id].referrals)
            if referral_count % 3 == 0:  # Каждые 3 приглашенных
                if referral_count <= 30:  # Максимум 10 карточек (30/3)
                    card_id = random.choice(card_pool)
                    users[referrer_id].cards[card_id] = users[referrer_id].cards.get(card_id, 0) + 1
                    
                    # Уведомляем о бонусе
                    try:
                        asyncio.create_task(send_referral_bonus(referrer_id, referral_count, card_id))
                    except:
                        pass
            
            save_data()
            logger.info(f"🎁 Новый пользователь {user_id} приглашен пользователем {referrer_id}")
        
        save_data()
        logger.info(f"✅ Создан новый пользователь: {user_id}")
    
    elif (username and users[user_id].username != username) or (first_name and users[user_id].first_name != first_name):
        if username:
            users[user_id].username = username
        if first_name:
            users[user_id].first_name = first_name
        save_data()
    
    update_user_interaction(users[user_id])
    
    return users[user_id]

def add_reduced_cd(user: User, days: int = 30):
    user.has_reduced_cd = True
    now = datetime.now()
    
    if user.reduced_cd_until:
        current_until = datetime.fromisoformat(user.reduced_cd_until)
        if current_until > now:
            user.reduced_cd_until = (current_until + timedelta(days=days)).isoformat()
        else:
            user.reduced_cd_until = (now + timedelta(days=days)).isoformat()
    else:
        user.reduced_cd_until = (now + timedelta(days=days)).isoformat()
    
    update_user_interaction(user)
    save_data()
    return True

def add_reduced_trade_cd(user: User, days: int = 30):
    user.has_reduced_trade_cd = True
    now = datetime.now()
    
    if user.reduced_trade_cd_until:
        current_until = datetime.fromisoformat(user.reduced_trade_cd_until)
        if current_until > now:
            user.reduced_trade_cd_until = (current_until + timedelta(days=days)).isoformat()
        else:
            user.reduced_trade_cd_until = (now + timedelta(days=days)).isoformat()
    else:
        user.reduced_trade_cd_until = (now + timedelta(days=days)).isoformat()
    
    update_user_interaction(user)
    save_data()
    return True

def add_cooldown(user: User, hours: int):
    user.last_card_time = datetime.now().isoformat()
    update_user_interaction(user)
    save_data()
    return True

def calculate_level_exp(level: int) -> int:
    base = LEVEL_SETTINGS['base_exp_per_level']
    multiplier = LEVEL_SETTINGS['exp_multiplier']
    return int(base * (multiplier ** (level - 1)))

def add_experience(user: User, action_type: str, amount: int = None):
    if not LEVEL_SETTINGS['enabled']:
        return
    
    if amount is None:
        amount = LEVEL_SETTINGS['exp_actions'].get(action_type, 0)
    
    if action_type == 'purchase_card':
        user.secret_total_spent += amount * 2
    
    user.experience += amount
    user.total_exp_earned += amount
    
    exp_needed = calculate_level_exp(user.level)
    while user.experience >= exp_needed and user.level < 100:
        user.experience -= exp_needed
        user.level += 1
        exp_needed = calculate_level_exp(user.level)
        
        reward = LEVEL_SETTINGS['level_rewards'].get(user.level)
        if reward:
            pass
    
    save_data()

def get_cooldown_by_level(user: User, is_premium: bool = None) -> float:
    if is_premium is None:
        is_premium = user.is_premium
    
    base_hours = 2 if is_premium else 4
    base_minutes = base_hours * 60
    
    reduction_minutes = (user.level - 1) * 2
    total_minutes = base_minutes - reduction_minutes
    
    total_minutes = max(30, total_minutes)
    
    return total_minutes / 60

def get_level_progress_bar(user: User, length: int = 10) -> str:
    exp_needed = calculate_level_exp(user.level)
    current_exp = user.experience
    
    percentage = (current_exp / exp_needed) * 100
    filled = int((current_exp / exp_needed) * length)
    empty = length - filled
    
    bar = "▰" * filled + "▱" * empty
    return f"{bar} {percentage:.1f}%"

def update_card_popularity(card_id: str, action: str = "view"):
    if card_id not in card_popularity:
        card_popularity[card_id] = {
            'purchases': 0,
            'views': 0,
            'last_purchased': None,
            'total_revenue': 0
        }
    
    if action == "purchase":
        card_popularity[card_id]['purchases'] += 1
        card_popularity[card_id]['last_purchased'] = datetime.now().isoformat()
    elif action == "view":
        card_popularity[card_id]['views'] += 1

def get_popular_cards(limit: int = 5) -> List[Dict]:
    popular = []
    for card_id, stats in card_popularity.items():
        card = cards.get(card_id)
        if card:
            score = stats['purchases'] * 3 + stats['views']
            popular.append({
                'card': card,
                'stats': stats,
                'score': score
            })
    
    popular.sort(key=lambda x: x['score'], reverse=True)
    return popular[:limit]

def get_top_spenders(period_days: int = 30, limit: int = 10) -> List[Dict]:
    period_ago = datetime.now() - timedelta(days=period_days)
    
    spenders = []
    for user in users.values():
        user_orders = [
            o for o in orders.values() 
            if o.user_id == user.user_id 
            and o.status == "confirmed"
            and datetime.fromisoformat(o.confirmed_at or o.created_at) >= period_ago
        ]
        
        total_spent = sum(o.price for o in user_orders)
        if total_spent > 0:
            spenders.append({
                'user': user,
                'total_spent': total_spent,
                'orders_count': len(user_orders)
            })
    
    spenders.sort(key=lambda x: x['total_spent'], reverse=True)
    return spenders[:limit]

def get_personal_recommendations(user_id: int, limit: int = 3) -> List[Dict]:
    user = users.get(user_id)
    if not user or not user.cards:
        return []
    
    purchased_cards = list(user.cards.keys())
    purchased_rarities = defaultdict(int)
    
    for card_id in purchased_cards:
        card = cards.get(card_id)
        if card:
            purchased_rarities[card.rarity] += 1
    
    if not purchased_rarities:
        return []
    
    favorite_rarity = max(purchased_rarities.items(), key=lambda x: x[1])[0]
    
    recommendations = []
    for card_id, card in cards.items():
        if card_id not in purchased_cards and card.rarity == favorite_rarity:
            if card_id in shop_items:
                item = shop_items[card_id]
                recommendations.append({
                    'card': card,
                    'price': item.price,
                    'reason': f"Любимая редкость: {get_rarity_name(favorite_rarity)}"
                })
    
    for rec in recommendations:
        popularity = card_popularity.get(rec['card'].card_id, {})
        rec['popularity_score'] = popularity.get('purchases', 0)
    
    recommendations.sort(key=lambda x: x['popularity_score'], reverse=True)
    return recommendations[:limit]

def get_card_cooldown_hours(user: User) -> int:
    if user.has_reduced_cd and user.reduced_cd_until:
        until_date = datetime.fromisoformat(user.reduced_cd_until)
        if until_date > datetime.now():
            return 2
    return 4

def get_trade_cooldown_hours(user: User) -> int:
    if user.has_reduced_trade_cd and user.reduced_trade_cd_until:
        until_date = datetime.fromisoformat(user.reduced_trade_cd_until)
        if until_date > datetime.now():
            return 2
    return 4

def can_open_card(user: User) -> Tuple[bool, Optional[str]]:
    if not user.last_card_time:
        return True, None
    
    last_time = datetime.fromisoformat(user.last_card_time)
    now = datetime.now()
    cooldown_hours = get_card_cooldown_hours(user)
    cooldown = timedelta(hours=cooldown_hours)
    
    if now - last_time < cooldown:
        remaining = cooldown - (now - last_time)
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return False, f"{hours}ч {minutes}м"
    
    return True, None

def can_trade(user: User) -> Tuple[bool, Optional[str]]:
    if not user.last_trade_time:
        return True, None
    
    last_time = datetime.fromisoformat(user.last_trade_time)
    now = datetime.now()
    cooldown_hours = get_trade_cooldown_hours(user)
    cooldown = timedelta(hours=cooldown_hours)
    
    if now - last_time < cooldown:
        remaining = cooldown - (now - last_time)
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return False, f"{hours}ч {minutes}м"
    
    return True, None

def open_card(user: User) -> Optional[Tuple[Card, str]]:
    if not card_pool:
        return None
    
    if user.is_premium:
        premium_pool = []
        for card_id, card in cards.items():
            if card.rarity == "basic":
                weight = 8
            elif card.rarity == "cool":
                weight = 6
            elif card.rarity == "legendary":
                weight = 4
            elif card.rarity == "vinyl figure":
                weight = 2
            else:
                weight = 1
            premium_pool.extend([card_id] * weight)
        card_id = random.choice(premium_pool)
    else:
        card_id = random.choice(card_pool)
    
    card = cards[card_id]
    
    user.cards[card_id] = user.cards.get(card_id, 0) + 1
    user.opened_packs += 1
    user.last_card_time = datetime.now().isoformat()
    update_user_interaction(user)
    
    add_experience(user, 'open_card')
    
    save_data()
    
    return card, card_id

def claim_daily_bonus(user: User) -> bool:
    if not user.is_premium:
        return False
    
    today = datetime.now().date().isoformat()
    
    if user.daily_bonus_claimed == today:
        return False
    
    for _ in range(3):
        result = open_card(user)
        if result:
            card, card_id = result
            user.cards[card_id] = user.cards.get(card_id, 0) + 1
    
    user.daily_bonus_claimed = today
    user.opened_packs += 3
    update_user_interaction(user)
    save_data()
    
    return True

def add_premium(user: User, days: int = 30):
    user.is_premium = True
    now = datetime.now()
    
    if user.premium_until:
        current_until = datetime.fromisoformat(user.premium_until)
        if current_until > now:
            user.premium_until = (current_until + timedelta(days=days)).isoformat()
        else:
            user.premium_until = (now + timedelta(days=days)).isoformat()
    else:
        user.premium_until = (now + timedelta(days=days)).isoformat()
    
    for _ in range(10):
        result = open_card(user)
        if result:
            card, card_id = result
            user.cards[card_id] = user.cards.get(card_id, 0) + 1
    
    update_user_interaction(user)
    save_data()
    return True

def generate_shop_card() -> Optional[Tuple[str, int]]:
    if not cards:
        return None
    
    rarity_weights = {
        "basic": 10,
        "cool": 5,
        "legendary": 2,
        "vinyl figure": 1
    }
    
    cards_by_rarity = {}
    for card_id, card in cards.items():
        if card.rarity in rarity_weights:
            if card.rarity not in cards_by_rarity:
                cards_by_rarity[card.rarity] = []
            cards_by_rarity[card.rarity].append(card_id)
    
    rarity_pool = []
    for rarity, weight in rarity_weights.items():
        if rarity in cards_by_rarity and cards_by_rarity[rarity]:
            rarity_pool.extend([rarity] * weight)
    
    if not rarity_pool:
        return None
    
    selected_rarity = random.choice(rarity_pool)
    card_id = random.choice(cards_by_rarity[selected_rarity])
    price = SHOP_PRICES.get(selected_rarity, 99)
    
    return card_id, price

def update_shop():
    global shop_items
    
    now = datetime.now()
    expired_cards = []
    for card_id, item in shop_items.items():
        expires_at = datetime.fromisoformat(item.expires_at)
        if expires_at <= now:
            expired_cards.append(card_id)
    
    for card_id in expired_cards:
        del shop_items[card_id]
    
    while len(shop_items) < 3:
        result = generate_shop_card()
        if result:
            card_id, price = result
            expires_at = now + timedelta(hours=12)
            shop_items[card_id] = ShopItem(
                card_id=card_id,
                price=price,
                expires_at=expires_at.isoformat()
            )
        else:
            break
    
    save_data()

def create_order(user: User, card_id: str, price: int) -> Optional[Order]:
    if card_id not in shop_items:
        return None
    
    user_pending_orders = [o for o in orders.values() 
                          if o.user_id == user.user_id 
                          and o.card_id == card_id 
                          and o.status == "pending"]
    if user_pending_orders:
        return None
    
    order_id = f"order_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    order = Order(order_id, user.user_id, card_id, price)
    orders[order_id] = order
    
    del shop_items[card_id]
    
    add_experience(user, 'purchase_card', price // 10)
    
    save_data()
    return order

def confirm_order(order_id: str, admin_id: int) -> bool:
    if order_id not in orders:
        logger.error(f"Заказ {order_id} не найден")
        return False
    
    order = orders[order_id]
    if order.status != "pending":
        logger.error(f"Заказ {order_id} имеет статус {order.status}, а не pending")
        return False
    
    user = users.get(order.user_id)
    if not user:
        logger.error(f"Пользователь {order.user_id} не найден")
        return False
    
    card = cards.get(order.card_id)
    if not card:
        logger.error(f"Карточка {order.card_id} не найден")
        return False
    
    try:
        if order.card_id not in user.cards:
            user.cards[order.card_id] = 1
        else:
            user.cards[order.card_id] += 1
        
        user.opened_packs += 1
        update_user_interaction(user)
        
        order.status = "confirmed"
        order.confirmed_at = datetime.now().isoformat()
        order.admin_id = admin_id
        
        update_card_popularity(order.card_id, "purchase")
        
        save_data()
        
        logger.info(f"Заказ {order_id} подтвержден. Карточка {order.card_id} выдана пользователю {user.user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения заказа {order_id}: {e}")
        return False

def reject_order(order_id: str, admin_id: int) -> bool:
    if order_id not in orders:
        return False
    
    order = orders[order_id]
    if order.status != "pending":
        return False
    
    order.status = "rejected"
    order.confirmed_at = datetime.now().isoformat()
    order.admin_id = admin_id
    
    if len(shop_items) < 3:
        expires_at = datetime.now() + timedelta(hours=12)
        shop_items[order.card_id] = ShopItem(
            card_id=order.card_id,
            price=order.price,
            expires_at=expires_at.isoformat()
        )
    
    save_data()
    return True

def create_trade(from_user_id: int, to_user_id: int, cards_to_give: List[str]) -> str:
    trade_id = f"trade_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    
    trade_data = {
        'id': trade_id,
        'from_user': from_user_id,
        'to_user': to_user_id,
        'cards': cards_to_give,
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'receiver_card': None,
        'completed_at': None
    }
    
    trades[trade_id] = trade_data
    save_data()
    
    return trade_id

def get_rarity_color(rarity: str) -> str:
    colors = {
        "basic": "⚪️",
        "cool": "🔵",
        "legendary": "🟡",
        "vinyl figure": "🟣"
    }
    return colors.get(rarity, "⚪️")

def get_rarity_name(rarity: str) -> str:
    names = {
        "basic": "Обычная",
        "cool": "Крутая",
        "legendary": "Легендарная",
        "vinyl figure": "Виниловая фигурка"
    }
    return names.get(rarity, rarity)

def get_image_path(card: Card) -> Optional[Path]:
    if not card.image_filename:
        return None
    
    filepath = IMAGES_DIR / card.image_filename
    if filepath.exists():
        return filepath
    return None

def get_main_menu():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="👤 Профиль"))
    keyboard.add(KeyboardButton(text="💝 Поддержать проект"))
    keyboard.add(KeyboardButton(text="🎴 Инвентарь"))
    keyboard.add(KeyboardButton(text="🔄 Обмен"))
    keyboard.add(KeyboardButton(text="🛒 Магазин"))
    keyboard.add(KeyboardButton(text="🎪 Эксклюзивы"))
    keyboard.add(KeyboardButton(text="❓ Помощь"))
    keyboard.add(KeyboardButton(text="🏆 Топ игроков"))
    keyboard.add(KeyboardButton(text="💰 Топ покупателей"))
    keyboard.adjust(3, 3, 3)
    return keyboard.as_markup(resize_keyboard=True)

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_card_name = State()
    waiting_for_card_rarity = State()
    waiting_for_card_image = State()
    waiting_for_premium_username = State()
    waiting_for_cooldown_username = State()
    waiting_for_add_cooldown_username = State()
    waiting_for_reduced_cd_username = State()
    waiting_for_reduced_trade_cd_username = State()
    waiting_for_card_id_to_delete = State()
    waiting_for_ban_username = State()
    waiting_for_ban_reason = State()
    waiting_for_ban_days = State()
    waiting_for_unban_username = State()
    waiting_for_freeze_username = State()
    waiting_for_freeze_days = State()
    waiting_for_unfreeze_username = State()
    waiting_for_order_id = State()

class TradeStates(StatesGroup):
    selecting_my_cards = State()
    selecting_partner = State()
    confirming_trade = State()

class OrderStates(StatesGroup):
    waiting_for_payment_proof = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Извлекаем referrer_id из параметров команды
    referrer_id = None
    if len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith('ref_'):
            try:
                referrer_id = int(args.replace('ref_', ''))
                # Проверяем, что это не сам пользователь и не фейковый ID
                if referrer_id == user_id or referrer_id < 1000:
                    referrer_id = None
            except:
                referrer_id = None
    
    # Создаем/получаем пользователя с учетом реферала
    user = get_or_create_user(
        message.from_user.id, 
        message.from_user.username,
        message.from_user.first_name,
        referrer_id  # Передаем referrer_id если есть
    )
    
    # Проверяем доступ
    if not await check_access_before_handle(message, user_id):
        return
    
    # Проверяем подписку
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        await message.answer(
            "👋 <b>Добро пожаловать в Funko Cards Bot!</b>\n\n"
            "⚠️ <b>Для использования бота необходимо подписаться на наш канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "1. Нажмите кнопку '📢 Подписаться на канал'\n"
            "2. Подпишитесь на канал\n"
            "3. Нажмите кнопку '✅ Я подписался'\n\n"
            "<i>Без подписки бот не будет работать</i>",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Добавляем информацию о рефералах если есть
    if user.referrer_id:
        referrer = users.get(user.referrer_id)
        if referrer:
            await message.answer(
                f"👋 <b>Добро пожаловать!</b>\n\n"
                f"Вас пригласил: @{referrer.username or 'друг'}\n"
                f"🎁 Вы получили: <b>100 XP бонус</b> за регистрацию по приглашению!\n\n"
                f"Теперь вы тоже можете приглашать друзей и получать бонусы!\n\n"
                f"💡 Используйте команду /invite чтобы получить свою ссылку"
            )
    
    if user.is_premium:
        claimed = claim_daily_bonus(user)
        if claimed:
            await message.answer("🎁 <b>Получен ежедневный бонус: 3 карточки!</b>")
    
    # Проверяем истекшие кулдауны
    if user.has_reduced_cd and user.reduced_cd_until:
        until_date = datetime.fromisoformat(user.reduced_cd_until)
        if until_date <= datetime.now():
            user.has_reduced_cd = False
            user.reduced_cd_until = None
            save_data()
    
    if user.has_reduced_trade_cd and user.reduced_trade_cd_until:
        until_date = datetime.fromisoformat(user.reduced_trade_cd_until)
        if until_date <= datetime.now():
            user.has_reduced_trade_cd = False
            user.reduced_trade_cd_until = None
            save_data()
    
    await message.answer(
        "🎮 <b>Добро пожаловать в мир карточек Фанко!</b>\n\n"
        "✅ <b>Вы успешно подписались на канал!</b>\n\n"
        "🎴 <b>Как получить карточку:</b>\n"
        "Просто напишите слово <b>фанко</b> в любом групповом чате с ботом!\n\n"
        "📱 <b>Основные возможности:</b>\n"
        "• 👤 Профиль - ваша статистика\n"
        "• 🎴 Инвентарь - все ваши карточки\n"
        "• 🔄 Обмен - обмен карточками с другими\n"
        "• 🛒 Магазин - покупка редких карточек\n"
        "• 💝 Поддержать проект - помочь развитию бота\n\n"
        "🎁 <b>Новое: Реферальная система!</b>\n"
        "Приглашайте друзей командой /invite и получайте бонусы!\n\n"
        "Используйте кнопки меню ниже:",
        reply_markup=get_main_menu()
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    await message.answer(
        "❓ <b>Помощь и инструкции</b>\n\n"
        "🎴 <b>Как получить карточку:</b>\n"
        "1. Добавьте бота в групповой чат\n"
        "2. Дайте боту права администратора\n"
        "3. Напишите слово <b>фанко</b> в чате\n"
        "4. Получите случайную карточку!\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/myorders - Мои заказы\n"
        "/payment - Отправить скриншот оплаты\n"
        "/refresh - Отменить текущее действие\n"
        "/admin - Админ-панель (только для админов)\n\n"
        "<i>Используйте кнопки меню для навигации</i>"
    )

@dp.message(Command("invite"))
async def invite_command(message: types.Message):
    """Команда для приглашения друзей"""
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    user = get_or_create_user(message.from_user.id)
    
    # Получаем username бота
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    # Создаем реферальную ссылку
    invite_link = f"https://t.me/{bot_username}?start=ref_{user.user_id}"
    
    # Создаем красивую клавиатуру
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="📢 Поделиться ссылкой", 
        url=f"https://t.me/share/url?url={invite_link}&text=🎴 Присоединяйся к игре Funko Cards! Собирай карточки, обменивайся с друзьями и получай редкие экземпляры!"
    ))
    keyboard.add(InlineKeyboardButton(
        text="👥 Мои рефералы", 
        callback_data="my_referrals"
    ))
    keyboard.adjust(1)
    
    # Статистика рефералов
    total_referrals = len(user.referrals)
    cards_earned = total_referrals // 3
    next_bonus_at = 3 - (total_referrals % 3) if total_referrals % 3 != 0 else 3
    
    await message.answer(
        f"🎁 <b>Приглашай друзей и получай бонусы!</b>\n\n"
        f"📊 <b>Твоя статистика:</b>\n"
        f"👥 Приглашено друзей: <b>{total_referrals}</b>\n"
        f"🎴 Получено карточек: <b>{cards_earned}</b>\n"
        f"✨ Всего заработано XP: <b>{total_referrals * 50}</b>\n\n"
        f"🎯 <b>До следующей карточки:</b> {next_bonus_at} приглашенных\n\n"
        f"📢 <b>Твоя ссылка для приглашения:</b>\n"
        f"<code>{invite_link}</code>\n\n"
        f"💡 <b>Как приглашать:</b>\n"
        f"1. Отправь другу ссылку выше\n"
        f"2. Друг нажимает на ссылку\n"
        f"3. Друг получает +100 XP сразу\n"
        f"4. Ты получаешь +50 XP\n"
        f"5. Каждые 3 друга - карточка в подарок!\n\n"
        f"🔥 <b>Бонус за 10 друзей:</b> ЛЕГЕНДАРНАЯ карточка!",
        reply_markup=keyboard.as_markup(),
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data == "my_referrals")
async def my_referrals_handler(callback: types.CallbackQuery):
    """Показывает список приглашенных друзей"""
    user = get_or_create_user(callback.from_user.id)
    
    if not user.referrals:
        await callback.answer("У вас пока нет приглашенных друзей", show_alert=True)
        return
    
    response = "👥 <b>Ваши приглашенные друзья:</b>\n\n"
    
    # Показываем последних 20 рефералов
    for i, ref_id in enumerate(user.referrals[-20:], 1):
        ref_user = users.get(ref_id)
        if ref_user:
            # Проверяем активность реферала
            last_seen = datetime.fromisoformat(ref_user.last_seen)
            days_ago = (datetime.now() - last_seen).days
            
            status = "🟢" if days_ago < 1 else "🟡" if days_ago < 7 else "🔴"
            username = f"@{ref_user.username}" if ref_user.username else f"Пользователь {ref_id}"
            
            response += f"{i}. {status} {username}\n"
    
    # Статистика
    total = len(user.referrals)
    active = len([r for r in user.referrals if users.get(r) and (datetime.now() - datetime.fromisoformat(users[r].last_seen)).days < 7])
    cards_earned = total // 3
    
    response += f"\n📊 <b>Статистика:</b>\n"
    response += f"• Всего приглашено: {total}\n"
    response += f"• Активных: {active}\n"
    response += f"• Карточек получено: {cards_earned}\n"
    response += f"• XP заработано: {total * 50}\n\n"
    
    response += f"<i>Показано последние 20 из {total} рефералов</i>"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    user = get_or_create_user(message.from_user.id)
    
    user_orders = [o for o in orders.values() if o.user_id == user.user_id]
    
    if not user_orders:
        await message.answer(
            "📋 <b>Ваши заказы</b>\n\n"
            "У вас пока нет заказов.\n"
            "Чтобы создать заказ, перейдите в магазин или раздел поддержки."
        )
        return
    
    user_orders.sort(key=lambda o: datetime.fromisoformat(o.created_at), reverse=True)
    
    response = f"📋 <b>Ваши заказы ({len(user_orders)})</b>\n\n"
    
    for i, order in enumerate(user_orders[:10], 1):
        card = cards.get(order.card_id)
        card_name = card.name if card else "Неизвестная карточка"
        
        created = datetime.fromisoformat(order.created_at).strftime('%d.%m.%Y %H:%M')
        
        if order.status == "pending":
            status_icon = "⏳"
        elif order.status == "confirmed":
            status_icon = "✅"
        elif order.status == "rejected":
            status_icon = "❌"
        else:
            status_icon = "❓"
        
        response += (
            f"{i}. <b>{status_icon} Заказ {order.order_id[-4:]}</b>\n"
            f"🎴 {card_name}\n"
            f"💰 {order.price}₽ | {status_icon} {order.status}\n"
            f"📅 {created}\n\n"
        )
    
    if len(user_orders) > 10:
        response += f"<i>Показаны последние 10 из {len(user_orders)} заказов</i>\n\n"
    
    response += (
        "ℹ️ <b>Статусы заказов:</b>\n"
        "⏳ pending - ожидает оплаты/проверки\n"
        "✅ confirmed - подтвержден, карточка в инвентаре\n"
        "❌ rejected - отклонен\n\n"
        "📸 <b>Чтобы отправить скриншот оплаты:</b>\n"
        "Используйте команду /payment"
    )
    
    await message.answer(response)

@dp.message(Command("refresh"))
async def cmd_refresh(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if not current_state:
        await message.answer(
            "🔄 <b>Нет активных действий для отмена</b>\n\n"
            "Вы не находитесь в процессе выполнения какой-либо команды."
        )
        return
    
    await state.clear()
    await message.answer(
        "✅ <b>Действие отменено!</b>\n\n"
        "Состояние очищено. Вы можете начать заново.\n"
        "Используйте команду /payment для отправки скриншота оплаты."
    )

@dp.message(Command("payment"))
async def payment_proof_command(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    await message.answer(
        "📤 <b>Отправка скриншота оплаты</b>\n\n"
        "1. Введите номер вашего заказа:\n"
        "<i>Пример: order_1700000000_1234</i>\n\n"
        "После ввода номера заказа отправьте скриншот оплаты."
    )
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(OrderStates.waiting_for_payment_proof, F.text)
async def process_order_id(message: types.Message, state: FSMContext):
    order_id = message.text.strip()
    
    if order_id.lower() == "/refresh":
        await state.clear()
        await message.answer(
            "✅ <b>Действие отменено!</b>\n\n"
            "Состояние очищено. Вы можете начать заново.\n"
            "Используйте команду /payment для отправки скриншота оплаты."
        )
        return
    
    if order_id not in orders:
        await message.answer(
            "❌ <b>Заказ не найден!</b>\n\n"
            "Проверьте правильность номера заказа.\n"
            "Номер заказа должен быть в формате:\n"
            "<code>order_1700000000_1234</code>\n\n"
            "Или используйте номер заказа который вы получили после покупки.\n\n"
            "📝 <b>Что можно сделать:</b>\n"
            "1. Проверьте номер заказа (он должен быть точной копией)\n"
            "2. Используйте команду /myorders чтобы посмотреть свои заказы\n"
            "3. Используйте команду <b>/refresh</b> чтобы отменить текущее действие\n"
            "4. Начните заново с команды /payment\n\n"
            "Попробуйте еще раз или напишите /refresh для отмены:"
        )
        return
    
    order = orders[order_id]
    
    if order.user_id != message.from_user.id:
        await message.answer(
            "❌ <b>Это не ваш заказ!</b>\n\n"
            "Вы можете отправлять скриншоты только для своих заказов.\n"
            "Проверьте номер заказа и попробуйте еще раз.\n\n"
            "ℹ️ <b>Подсказки:</b>\n"
            "• Используйте /myorders чтобы посмотреть свои заказы\n"
            "• Используйте <b>/refresh</b> чтобы отменить текущее действие\n\n"
            "Введите правильный номер заказа или /refresh:"
        )
        return
    
    if order.status != "pending":
        await message.answer(
            f"❌ <b>Заказ уже обработан!</b>\n\n"
            f"Статус заказа: {order.status}\n"
            f"Номер заказа: <code>{order_id}</code>\n\n"
            f"ℹ️ <b>Что это значит:</b>\n"
            f"• ✅ <b>confirmed</b> - заказ подтвержден, карточка в инвентаре\n"
            f"• ❌ <b>rejected</b> - заказ отклонен\n\n"
            f"Если вы считаете это ошибкой, напишите администратору: @prikolovwork\n\n"
            f"Используйте команду <b>/refresh</b> чтобы отменить текущее действие и начать заново."
        )
        return
    
    card = cards.get(order.card_id)
    if not card:
        await message.answer(
            "❌ Ошибка: карточка не найдена. Свяжитесь с администратором @prikolovwork\n\n"
            "Используйте команду <b>/refresh</b> чтобы отменить текущее действие."
        )
        return
    
    await state.update_data(order_id=order_id)
    await message.answer(
        f"✅ <b>Заказ найден!</b>\n\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n"
        f"🎴 <b>Карточка:</b> {card.name}\n"
        f"💰 <b>Сумма:</b> {order.price}₽\n\n"
        "Теперь отправьте скриншот оплаты.\n\n"
        "<i>Убедитесь, что на скриншоте видно:</i>\n"
        "• Номер карты получателя\n"
        "• Сумма перевода\n"
        "• Дата и время перевода\n"
        "• Статус 'Успешно'\n\n"
        "ℹ️ <b>Чтобы отменить:</b> напишите <b>/refresh</b>"
    )

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        await message.answer(
            "❌ <b>Сначала введите номер заказа!</b>\n\n"
            "Используйте команду /payment и следуйте инструкциям.\n"
            "Сначала введите номер заказа, затем отправьте скриншот."
        )
        await state.clear()
        return
    
    if order_id not in orders:
        await message.answer(
            "❌ <b>Заказ не найден!</b>\n\n"
            "Возможно, номер заказа был введен неверно.\n"
            "Попробуйте еще раз с начала: используйте /payment"
        )
        await state.clear()
        return
    
    order = orders[order_id]
    
    if order.user_id != message.from_user.id:
        await message.answer(
            "❌ <b>Это не ваш заказ!</b>\n\n"
            "Вы можете отправлять скриншоты только для своих заказов."
        )
        await state.clear()
        return
    
    if order.status != "pending":
        await message.answer(
            f"❌ <b>Заказ уже обработан!</b>\n\n"
            f"Статус заказа: {order.status}\n"
            f"Номер заказа: <code>{order_id}</code>"
        )
        await state.clear()
        return
    
    card = cards.get(order.card_id)
    card_name = card.name if card else "Неизвестная карточка"
    
    order.payment_proof = message.photo[-1].file_id
    
    save_data()
    
    await message.answer(
        "✅ <b>Скриншот получен!</b>\n\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n"
        f"🎴 <b>Карточка:</b> {card_name}\n"
        f"💰 <b>Сумма:</b> {order.price}₽\n\n"
        "📤 <b>Скриншот отправлен администраторам для проверки.</b>\n\n"
        "⏳ <b>Что дальше:</b>\n"
        "• Администратор проверит скриншот\n"
        "• Обычно это занимает до 24 часов\n"
        "• После подтверждения карточка появится в вашем инвентаре\n\n"
        "<i>Для ускорения процесса вы можете написать администратору: @prikolovwork</i>"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=order.payment_proof,
                caption=(
                    f"📤 <b>Новый скриншот оплаты!</b>\n\n"
                    f"🆔 <b>Заказ:</b> {order_id}\n"
                    f"👤 <b>Пользователь:</b> @{message.from_user.username or 'без username'} (ID: {message.from_user.id})\n"
                    f"🎴 <b>Карточка:</b> {card_name}\n"
                    f"💰 <b>Сумма:</b> {order.price}₽\n"
                    f"📅 <b>Время отправки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    f"<i>Для подтверждения нажмите кнопку ниже</i>"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_order_{order_id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{order_id}")
                    ],
                    [
                        InlineKeyboardButton(text="👁️ Просмотреть заказ", callback_data=f"view_order_{order_id}")
                    ]
                ])
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📤 <b>Новый скриншот оплаты (ошибка отправки фото)!</b>\n\n"
                        f"🆔 <b>Заказ:</b> {order_id}\n"
                        f"👤 <b>Пользователь:</b> @{message.from_user.username or 'без username'}\n"
                        f"🎴 <b>Карточка:</b> {card_name}\n"
                        f"💰 <b>Сумма:</b> {order.price}₽\n\n"
                        f"<i>Скриншот был отправлен, но не удалось переслать его. Проверьте заказ в админ-панели.</i>"
                    )
                )
            except Exception as e2:
                logger.error(f"Ошибка отправки текстового уведомления админу {admin_id}: {e2}")
    
    await state.clear()

@dp.message(OrderStates.waiting_for_payment_proof, F.text)
async def process_text_during_payment(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    
    if text in ["/refresh", "отмена", "cancel", "стоп", "stop"]:
        await state.clear()
        await message.answer(
            "✅ <b>Действие отменено!</b>\n\n"
            "Состояние очищено. Вы можете начать заново.\n"
            "Используйте команду /payment для отправки скриншота оплаты."
        )
        return
    
    await message.answer(
        "📸 <b>Ожидается скриншот оплаты!</b>\n\n"
        "Отправьте скриншот оплаты (фото).\n\n"
        "ℹ️ <b>Если хотите отменить:</b>\n"
        "• Напишите <b>/refresh</b>\n"
        "• Или напишите <b>отмена</b>\n\n"
        "<i>Пришлите фото скриншота оплаты...</i>"
    )

    # =============== ОБРАБОТЧИКИ ОБМЕНА ===============
@dp.callback_query(lambda c: c.data == "cancel_trade")
async def cancel_trade_handler(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания обмена"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Создание обмена отменено</b>\n\n"
        "Вы можете начать заново, нажав кнопку '📝 Создать предложение'"
    )
    await callback.answer()

@dp.message(TradeStates.selecting_partner)
async def process_trade_partner(message: types.Message, state: FSMContext):
    """Обработка username партнера для обмена"""
    if not await check_access_before_handle(message, message.from_user.id):
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    
    # Если пользователь написал /refresh
    if username.lower() == "/refresh":
        await state.clear()
        await message.answer("✅ <b>Действие отменено!</b>")
        return
    
    # Находим пользователя по username
    partner = get_user_by_username(username)
    
    if not partner:
        await message.answer(
            f"❌ <b>Пользователь @{username} не найден!</b>\n\n"
            f"Проверьте правильность написания username и убедитесь, что пользователь зарегистрирован в боте.\n\n"
            f"Попробуйте еще раз или напишите <b>/refresh</b> для отмены:"
        )
        return
    
    # Нельзя предлагать обмен самому себе
    if partner.user_id == message.from_user.id:
        await message.answer(
            "❌ <b>Нельзя предлагать обмен самому себе!</b>\n\n"
            "Введите username другого пользователя или напишите <b>/refresh</b> для отмены:"
        )
        return
    
    user = get_or_create_user(message.from_user.id)
    
    # Проверяем, есть ли у пользователя карточки для обмена
    if not user.cards:
        await message.answer(
            "❌ <b>У вас нет карточек для обмена!</b>\n\n"
            "Сначала получите карточки, написав <b>фанко</b> в групповом чате с ботом."
        )
        await state.clear()
        return
    
    # Проверяем кулдаун обменов у отправителя
    can_trade_now, remaining = can_trade(user)
    if not can_trade_now:
        await message.answer(
            f"⏰ <b>Вы можете создать обмен через {remaining}</b>\n\n"
            f"Кулдаун обменов: {get_trade_cooldown_hours(user)} часа"
        )
        await state.clear()
        return
    
    # Проверяем кулдаун обменов у получателя
    partner_can_trade, partner_remaining = can_trade(partner)
    if not partner_can_trade:
        await message.answer(
            f"⏰ <b>Пользователь @{partner.username} не может принимать обмены!</b>\n\n"
            f"Он сможет принимать обмены через {partner_remaining}\n"
            f"Кулдаун обменов: {get_trade_cooldown_hours(partner)} часа"
        )
        await state.clear()
        return
    
    # Сохраняем данные партнера
    await state.update_data(
        partner_id=partner.user_id,
        partner_username=partner.username
    )
    
    # Создаем клавиатуру с карточками пользователя
    keyboard = InlineKeyboardBuilder()
    
    for card_id, quantity in user.cards.items():
        if quantity > 0:  # Только карточки, которые есть в наличии
            card = cards.get(card_id)
            if card:
                rarity_icon = get_rarity_color(card.rarity)
                keyboard.add(InlineKeyboardButton(
                    text=f"{rarity_icon} {card.name} (x{quantity})",
                    callback_data=f"select_trade_card_{card_id}"
                ))
    
    keyboard.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_trade"
    ))
    keyboard.adjust(1)
    
    await message.answer(
        f"📝 <b>Создание обмена с @{partner.username}</b>\n\n"
        f"Теперь выберите карточки, которые хотите предложить для обмена:\n\n"
        f"<i>Выберите карточку из списка ниже</i>",
        reply_markup=keyboard.as_markup()
    )
    
    await state.set_state(TradeStates.selecting_my_cards)

@dp.callback_query(lambda c: c.data.startswith("select_trade_card_"), TradeStates.selecting_my_cards)
async def select_trade_card_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора карточки для обмена"""
    card_id = callback.data.replace("select_trade_card_", "")
    
    user = get_or_create_user(callback.from_user.id)
    data = await state.get_data()
    partner_id = data.get('partner_id')
    
    if not partner_id:
        await callback.answer("❌ Ошибка: партнер не найден", show_alert=True)
        await state.clear()
        return
    
    # Проверяем, есть ли такая карточка у пользователя
    if card_id not in user.cards or user.cards[card_id] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True)
        return
    
    card = cards.get(card_id)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return
    
    # Создаем обмен
    cards_to_give = [card_id]
    trade_id = create_trade(callback.from_user.id, partner_id, cards_to_give)
    
    # Обновляем кулдаун обменов у отправителя
    user.last_trade_time = datetime.now().isoformat()
    update_user_interaction(user)
    save_data()
    
    await callback.message.edit_text(
        f"✅ <b>Предложение обмена создано!</b>\n\n"
        f"🔄 <b>Обмен #{trade_id.split('_')[1]}</b>\n"
        f"👤 <b>Для:</b> @{data.get('partner_username', 'пользователь')}\n"
        f"🎴 <b>Вы предлагаете:</b> {card.name}\n"
        f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<i>Ожидайте подтверждения от пользователя</i>"
    )
    
    # Уведомляем получателя
    partner = get_or_create_user(partner_id)
    try:
        await bot.send_message(
            partner_id,
            f"📥 <b>Новое предложение обмена!</b>\n\n"
            f"🔄 <b>Обмен #{trade_id.split('_')[1]}</b>\n"
            f"👤 <b>От:</b> @{user.username or 'пользователь'}\n"
            f"🎴 <b>Предлагает:</b> {card.name}\n\n"
            f"Для просмотра перейдите в раздел 🔄 Обмен → 📥 Входящие предложения"
        )
    except:
        pass
    
    await state.clear()
    await callback.answer(f"Вы выбрали: {card.name}")
    
@dp.callback_query(lambda c: c.data == "check_subscription")
async def process_check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    user = users.get(user_id)
    if user:
        has_access, reason = check_user_access(user)
        if not has_access:
            await callback.answer(f"⛔ Доступ запрещен: {reason}", show_alert=True)
            return
    
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        await callback.answer(
            "❌ Вы еще не подписались на канал! Нажмите кнопку 'Подписаться на канал' и подпишитесь.",
            show_alert=True
        )
        return
    
    user = get_or_create_user(
        callback.from_user.id, 
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    if user.is_premium:
        claimed = claim_daily_bonus(user)
        if claimed:
            await callback.message.answer("🎁 <b>Получен ежедневный бонус: 3 карточки!</b>")
    
    await callback.message.edit_text(
        "✅ <b>Отлично! Вы подписаны на канал!</b>\n\n"
        "Теперь вы можете пользоваться ботом.\n"
        "Используйте кнопки меню для навигации."
    )
    
    await callback.message.answer(
        "🎮 <b>Добро пожаловать в мир карточек Фанко!</b>\n\n"
        "🎴 <b>Как получить карточку:</b>\n"
        "Просто напишите слово <b>фанко</b> в любом групповом чате с ботом!\n\n"
        "📱 <b>Основные возможности:</b>\n"
        "• 👤 Профиль - ваша статистика\n"
        "• 🎴 Инвентарь - все ваши карточки\n"
        "• 🔄 Обмен - обмен карточками с другими\n"
        "• 🛒 Магазин - покупка редких карточек\n"
        "• 💝 Поддержать проект - помочь развитию бота\n\n"
        "Используйте кнопки меню ниже:",
        reply_markup=get_main_menu()
    )
    
    await callback.answer()

@dp.message(F.text.contains("фанко"))
async def open_fanco(message: types.Message):
    text = message.text.lower().strip()
    
    if text not in ['фанко', 'fanco', 'фанк', 'фанка', 'фанку']:
        return
    
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    user_id = message.from_user.id
    
    user = users.get(user_id)
    if user:
        has_access, reason = check_user_access(user)
        if not has_access:
            await message.reply(f"⛔ <b>Доступ запрещен!</b>\n\n{reason}")
            return
    
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await message.reply(
            f"❌ <b>Для получения карточек необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки напишите /start боту в личные сообщения."
        )
        return
    
    user = get_or_create_user(
        user_id, 
        message.from_user.username,
        message.from_user.first_name
    )
    
    can_open, remaining = can_open_card(user)
    if not can_open:
        cooldown_hours = get_card_cooldown_hours(user)
        await message.reply(f"⏰ <b>Подождите еще {remaining}</b> перед открытием следующей карточки!\n(Кулдаун: {cooldown_hours} часа)")
        return
    
    result = open_card(user)
    if not result:
        await message.reply("❌ <b>Ошибка!</b> Нет доступных карточек.")
        return
    
    card, card_id = result
    
    rarity_icon = get_rarity_color(card.rarity)
    cooldown_hours = get_card_cooldown_hours(user)
    response = f"🎴 <b>{message.from_user.first_name}, вы получили карточку!</b>\n\n"
    response += f"{rarity_icon} <b>{card.name}</b>\n"
    response += f"📊 Редкость: {get_rarity_name(card.rarity)}\n"
    response += f"📈 Всего карточек: {sum(user.cards.values())}\n\n"
    response += f"⏰ <i>Следующая карточка через {cooldown_hours} часа</i>"
    
    image_path = get_image_path(card)
    if image_path and os.path.exists(image_path):
        try:
            await message.reply_photo(
                photo=FSInputFile(image_path),
                caption=response
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await message.reply(response)
    else:
        await message.reply(response)

@dp.message(F.text == "👤 Профиль")
async def profile_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к профилю необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    user = get_or_create_user(
        message.from_user.id, 
        message.from_user.username,
        message.from_user.first_name
    )
    
    rarity_stats = {}
    for card_id, quantity in user.cards.items():
        card = cards.get(card_id)
        if card:
            rarity_stats[card.rarity] = rarity_stats.get(card.rarity, 0) + quantity
    
    total_percentage = (len(user.cards) / len(cards)) * 100 if cards else 0
    
    can_open, remaining = can_open_card(user)
    card_cooldown_hours = get_card_cooldown_hours(user)
    card_cooldown_status = "✅ Готов к открытию" if can_open else f"⏰ Ждать: {remaining}"
    
    can_trade_now, trade_remaining = can_trade(user)
    trade_cooldown_hours = get_trade_cooldown_hours(user)
    trade_cooldown_status = "✅ Можно обмениваться" if can_trade_now else f"⏰ Ждать: {trade_remaining}"
    
    response = (
        f"👤 <b>Профиль {message.from_user.first_name}</b>\n\n"
        f"📊 <b>Основная статистика:</b>\n"
        f"🎴 Открыто карточек: {user.opened_packs}\n"
        f"📚 Всего карточек: {sum(user.cards.values())}\n"
        f"⭐ Уникальных карточек: {len(user.cards)}\n"
        f"📈 Процент коллекции: {total_percentage:.1f}%\n\n"
        f"⏰ <b>Кулдаун карточек ({card_cooldown_hours}ч):</b> {card_cooldown_status}\n"
        f"🔄 <b>Кулдаун обменов ({trade_cooldown_hours}ч):</b> {trade_cooldown_status}\n"
    )
    
    if user.is_premium:
        if user.premium_until:
            until_date = datetime.fromisoformat(user.premium_until)
            days_left = max(0, (until_date - datetime.now()).days)
            response += f"💎 <b>Премиум активен!</b> (осталось {days_left} дней)\n"
    
    if user.has_reduced_cd and user.reduced_cd_until:
        until_date = datetime.fromisoformat(user.reduced_cd_until)
        days_left = max(0, (until_date - datetime.now()).days)
        response += f"⚡ <b>Уменьшенный кулдаун карточек!</b> (осталось {days_left} дней)\n"
    
    if user.has_reduced_trade_cd and user.reduced_trade_cd_until:
        until_date = datetime.fromisoformat(user.reduced_trade_cd_until)
        days_left = max(0, (until_date - datetime.now()).days)
        response += f"🔄 <b>Уменьшенный кулдаун обменов!</b> (осталось {days_left} дней)\n"
    
    response += f"\n<b>Карточки по редкостям:</b>\n"
    
    for rarity in ["vinyl figure", "legendary", "cool", "basic"]:
        count = rarity_stats.get(rarity, 0)
        icon = get_rarity_color(rarity)
        name = get_rarity_name(rarity)
        response += f"{icon} {name}: {count} шт.\n"
    
    if LEVEL_SETTINGS['enabled']:
        cooldown_hours = get_cooldown_by_level(user, user.is_premium)
        progress_bar = get_level_progress_bar(user)
        
        response += f"\n🎮 <b>Уровень {user.level}</b>\n"
        response += f"📊 Прогресс: {progress_bar}\n"
        response += f"⏱️ Ваш кулдаун: {cooldown_hours:.1f}ч\n"
        
        next_level_exp = calculate_level_exp(user.level)
        exp_needed = next_level_exp - user.experience
        response += f"🎯 До {user.level + 1} уровня: {exp_needed} XP\n"
    
    recommendations = get_personal_recommendations(message.from_user.id, 2)
    if recommendations:
        response += "\n🎯 <b>Вам может понравиться:</b>\n"
        for rec in recommendations:
            card = rec['card']
            rarity_icon = get_rarity_color(card.rarity)
            response += f"{rarity_icon} {card.name} - {rec['price']}₽\n"
        response += "<i>На основе ваших предпочтений</i>\n"
    
    await message.answer(response)

@dp.message(F.text == "💝 Поддержать проект")
async def support_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к покупкам необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="💎 Купить премиум", 
        callback_data="buy_premium"
    ))
    keyboard.add(InlineKeyboardButton(
        text="⚡ Снизить кулдаун карточек", 
        callback_data="buy_reduced_cd"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔄 Снизить кулдаун обменов", 
        callback_data="buy_reduced_trade_cd"
    ))
    keyboard.add(InlineKeyboardButton(
        text="💰 Поддержать проект", 
        url="https://tbank.ru/cf/17LdZPej2CV"
    ))
    keyboard.add(InlineKeyboardButton(
        text="📞 Связь с автором", 
        url="https://t.me/prikolovwork"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="back_to_menu"
    ))
    keyboard.adjust(2)
    
    await message.answer(
        f"💝 <b>Поддержать проект</b>\n\n"
        f"Вы можете поддержать развитие бота:\n\n"
        f"💰 <b>Разовое пожертвование:</b>\n"
        f"Любая сумма на развитие проекта\n\n"
        f"💎 <b>Премиум подписка ({PREMIUM_COST}₽/месяц):</b>\n"
        f"• Удвоенный шанс на редкие карты\n"
        f"• 10 карточки при подключении\n"
        f"• Ежедневный бонус: 3 карточки\n\n"
        f"⚡ <b>Снизить кулдаун карточек ({REDUCED_CD_COST}₽/месяц):</b>\n"
        f"После покупки этой функции ваш кулдаун сократится с 4х часов до 2х!\n\n"
        f"🔄 <b>Снизить кулдаун обменов ({REDUCED_TRADE_CD_COST}₽/месяц):</b>\n"
        f"Кулдаун обменов сократится с 4х часов до 2х!\n\n"
        f"После оплаты отправьте скриншот: @prikolovwork",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "buy_premium")
async def buy_premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    
    await show_payment_methods(
        callback=callback,
        product_type="premium",
        product_id="premium_30_days",
        price=PREMIUM_COST,
        description="Премиум подписка на 1 месяц"
    )

@dp.callback_query(lambda c: c.data == "buy_reduced_cd")
async def buy_reduced_cd_handler(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_or_create_user(callback.from_user.id)
    
    order_id = f"reduced_cd_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    
    order = Order(order_id, user.user_id, "reduced_cd_30_days", REDUCED_CD_COST)
    orders[order_id] = order
    save_data()
    
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Уменьшенный кулдаун карточек на 1 месяц\n"
        f"💰 <b>Сумма:</b> {REDUCED_CD_COST}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )
    
    await show_payment_methods(
        callback=callback,
        product_type="reduced_cd",
        product_id="reduced_cd_30_days",
        price=REDUCED_CD_COST,
        description="Уменьшенный кулдаун карточек на 1 месяц"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"⚡ <b>Новый заказ на уменьшенный кулдаун!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Уменьшенный кулдаун карточек на 30 дней\n"
                     f"💰 <b>Сумма:</b> {REDUCED_CD_COST}₽\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@dp.callback_query(lambda c: c.data == "buy_reduced_trade_cd")
async def buy_reduced_trade_cd_handler(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_or_create_user(callback.from_user.id)
    
    order_id = f"reduced_trade_cd_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    
    order = Order(order_id, user.user_id, "reduced_trade_cd_30_days", REDUCED_TRADE_CD_COST)
    orders[order_id] = order
    save_data()
    
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Уменьшенный кулдаун обменов на 1 месяц\n"
        f"💰 <b>Сумма:</b> {REDUCED_TRADE_CD_COST}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )
    
    await show_payment_methods(
        callback=callback,
        product_type="reduced_trade_cd",
        product_id="reduced_trade_cd_30_days",
        price=REDUCED_TRADE_CD_COST,
        description="Уменьшенный кулдаун обменов на 1 месяц"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🔄 <b>Новый заказ на уменьшенный кулдаун обменов!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Уменьшенный кулдаун обменов на 30 дней\n"
                     f"💰 <b>Сумма:</b> {REDUCED_TRADE_CD_COST}₽\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@dp.callback_query(lambda c: c.data.startswith("payment_method:"))
async def payment_method_handler(callback: types.CallbackQuery):
    await callback.answer()
    
    data = callback.data.split(":")
    if len(data) < 5:
        await callback.message.answer("❌ Ошибка в данных оплаты")
        return
    
    method = data[1]
    product_type = data[2]
    product_id = data[3]
    price = int(data[4])
    
    product_names = {
        "premium": "Премиум подписка на 1 месяц",
        "reduced_cd": "Уменьшенный кулдаун карточек на 1 месяц", 
        "reduced_trade_cd": "Уменьшенный кулдаун обменов на 1 месяц",
        "shop_card": "Карточка из магазина",
        "exclusive_card": "Эксклюзивная карточка"
    }
    
    product_name = product_names.get(product_type, "Товар")
    
    if product_type in ["shop_card", "exclusive_card"]:
        card = cards.get(product_id)
        if card:
            rarity_icon = get_rarity_color(card.rarity)
            product_name = f"{rarity_icon} {card.name} ({get_rarity_name(card.rarity)})"
    
    user = get_or_create_user(callback.from_user.id)
    user_orders = [o for o in orders.values() 
                   if o.user_id == user.user_id 
                   and o.card_id == product_id 
                   and o.status == "pending"]
    
    if user_orders:
        order = user_orders[-1]
        order_id = order.order_id
    else:
        if product_type not in ["shop_card", "exclusive_card"]:
            order_id = f"{product_type}_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
            order = Order(order_id, user.user_id, product_id, price)
            orders[order_id] = order
            save_data()
        else:
            order_id = "НЕИЗВЕСТНО"
    
    if method == "transfer":
        await callback.message.answer(
            f"🏦 <b>Оплата переводом на Т-Банк</b>\n\n"
            f"🎁 <b>Товар:</b> {product_name}\n"
            f"💰 <b>Сумма:</b> {price}₽\n"
            f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
            f"📱 <b>Реквизиты для перевода:</b>\n"
            f"<code>2200 7021 2881 4568</code>\n\n"
            f"💳 <b>Инструкция:</b>\n"
            f"1. Откройте приложение Т-Банк\n"
            f"2. Выберите 'Перевод по номеру карты'\n"
            f"3. Введите номер карты: <code>2200 7021 2881 4568</code>\n"
            f"4. Укажите сумму: {price}₽\n"
            f"5. В комментарии укажите: Заказ {order_id}\n"
            f"6. Подтвердите перевод\n\n"
            f"📸 <b>После оплаты:</b>\n"
            f"1. Сделайте скриншот перевода\n"
            f"2. Используйте команду /payment\n"
            f"3. Введите номер заказа: <code>{order_id}</code>\n"
            f"4. Отправьте скриншот\n\n"
            f"<i>При возникновении вопросов пишите: @prikolovwork</i>",
            parse_mode="HTML"
        )
    
    elif method == "link":
        await callback.message.answer(
            f"🔗 <b>Оплата по ссылке</b>\n\n"
            f"🎁 <b>Товар:</b> {product_name}\n"
            f"💰 <b>Сумма:</b> {price}₽\n"
            f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
            f"🌐 <b>Ссылка для оплаты:</b>\n"
            f"<a href='https://tbank.ru/cf/17LdZPej2CV'>https://tbank.ru/cf/17LdZPej2CV</a>\n\n"
            f"📱 <b>Инструкция:</b>\n"
            f"1. Нажмите на ссылку выше\n"
            f"2. Введите сумму: {price}₽\n"
            f"3. В комментарии укажите: Заказ {order_id}\n"
            f"4. Заполните данные для оплаты\n"
            f"5. Подтвердите оплату\n\n"
            f"📸 <b>После оплата:</b>\n"
            f"1. Сделайте скриншот подтверждения оплаты\n"
            f"2. Используйте команду /payment\n"
            f"3. Введите номер заказа: <code>{order_id}</code>\n"
            f"4. Отправьте скриншот\n\n"
            f"<i>При возникновении вопросов пишите: @prikolovwork</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    
    elif method == "admin":
        await callback.message.answer(
            f"👨‍💼 <b>Оплата через администратора</b>\n\n"
            f"🎁 <b>Товар:</b> {product_name}\n"
            f"💰 <b>Сумма:</b> {price}₽\n"
            f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
            f"📱 <b>Инструкция:</b>\n"
            f"1. Напишите администратору: @prikolovwork\n"
            f"2. Укажите номер заказа: <code>{order_id}</code>\n"
            f"3. Укажите что хотите купить: {product_name}\n"
            f"4. Обсудите удобный способ оплаты\n"
            f"5. Получите индивидуальные реквизиты\n"
            f"6. Совершите оплату\n\n"
            f"<i>Этот способ подходит если у вас:\n"
            f"• Другой банк\n"
            f"• Проблемы с переводом\n"
            f"• Хотите оплатить другими способами</i>\n\n"
            f"⏱️ <b>Время обработки:</b>\n"
            f"• Обычно в течение 1-2 часов\n"
            f"• В рабочее время быстрее",
            parse_mode="HTML"
        )

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.message.answer(
        "🔙 <b>Возвращаемся в главное меню</b>\n\n"
        "Используйте кнопки меню для навигации:",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.message(F.text == "🛒 Магазин")
async def shop_menu_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к магазину необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    update_shop()
    
    if not shop_items:
        await message.answer(
            "🛒 <b>Магазин карточек</b>\n\n"
            "В магазине пока нет доступных карточек.\n\n"
            "Новые карточки появляются каждые 12 часов.\n"
            "Проверьте позже!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="shop_refresh")]
            ])
        )
        return
    
    keyboard = InlineKeyboardBuilder()
    
    for card_id, item in shop_items.items():
        card = cards.get(card_id)
        if card:
            rarity_icon = get_rarity_color(card.rarity)
            expires_at = datetime.fromisoformat(item.expires_at)
            time_left = expires_at - datetime.now()
            hours_left = max(0, int(time_left.total_seconds() // 3600))
            
            keyboard.add(InlineKeyboardButton(
                text=f"{rarity_icon} {card.name} - {item.price}₽ ({hours_left}ч)",
                callback_data=f"shop_buy_{card_id}"
            ))
    
    keyboard.add(InlineKeyboardButton(
        text="🔄 Обновить магазин", 
        callback_data="shop_refresh"
    ))
    keyboard.add(InlineKeyboardButton(
        text="❓ Как работает магазин", 
        callback_data="shop_help"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="back_to_menu"
    ))
    keyboard.adjust(1)
    
    user = get_or_create_user(message.from_user.id)
    last_check = ""
    if user.last_shop_check:
        last_check_time = datetime.fromisoformat(user.last_shop_check)
        last_check = f"\n🕐 <b>Последняя проверка:</b> {last_check_time.strftime('%d.%m.%Y %H:%M')}"
    
    await message.answer(
        f"🛒 <b>Магазин карточек</b>\n\n"
        f"Доступно карточек: {len(shop_items)}\n"
        f"🕐 <b>Обновление:</b> каждые 12 часов{last_check}\n\n"
        f"<b>Цены по редкостям:</b>\n"
        f"⚪️ Обычная: {SHOP_PRICES['basic']}₽\n"
        f"🔵 Крутая: {SHOP_PRICES['cool']}₽\n"
        f"🟡 Легендарная: {SHOP_PRICES['legendary']}₽\n"
        f"🟣 Виниловая фигурка: {SHOP_PRICES['vinyl figure']}₽\n\n"
        f"<b>Доступные карточки:</b>",
        reply_markup=keyboard.as_markup()
    )
    
    user.last_shop_check = datetime.now().isoformat()
    save_data()

@dp.callback_query(lambda c: c.data == "shop_refresh")
async def shop_refresh_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    user = get_or_create_user(callback.from_user.id)
    
    update_shop()
    user.last_shop_check = datetime.now().isoformat()
    save_data()
    
    await callback.answer("🛒 Магазин обновлен!")
    
    if not shop_items:
        await callback.message.edit_text(
            "🛒 <b>Магазин карточек</b>\n\n"
            "В магазине пока нет доступных карточек.\n\n"
            "Новые карточки появляются каждые 12 часов.\n"
            "Проверьте позже!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="shop_refresh")]
            ])
        )
        return
    
    keyboard = InlineKeyboardBuilder()
    
    for card_id, item in shop_items.items():
        card = cards.get(card_id)
        if card:
            rarity_icon = get_rarity_color(card.rarity)
            expires_at = datetime.fromisoformat(item.expires_at)
            time_left = expires_at - datetime.now()
            hours_left = max(0, int(time_left.total_seconds() // 3600))
            
            keyboard.add(InlineKeyboardButton(
                text=f"{rarity_icon} {card.name} - {item.price}₽ ({hours_left}ч)",
                callback_data=f"shop_buy_{card_id}"
            ))
    
    keyboard.add(InlineKeyboardButton(
        text="🔄 Обновить магазин", 
        callback_data="shop_refresh"
    ))
    keyboard.add(InlineKeyboardButton(
        text="❓ Как работает магазин", 
        callback_data="shop_help"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="back_to_menu"
    ))
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        f"🛒 <b>Магазин карточек (обновлено)</b>\n\n"
        f"Доступно карточек: {len(shop_items)}\n"
        f"🕐 <b>Обновление:</b> каждые 12 часов\n"
        f"🕐 <b>Последняя проверка:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Доступные карточки:</b>",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("shop_buy_"))
async def shop_buy_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("shop_buy_", "")
    
    if card_id not in shop_items:
        await callback.answer("❌ Карточка уже куплена!", show_alert=True)
        return
    
    user = get_or_create_user(callback.from_user.id)
    item = shop_items[card_id]
    card = cards.get(card_id)
    
    if not card:
        await callback.answer("❌ Карточка не найдена!", show_alert=True)
        return
    
    user_pending_orders = [o for o in orders.values() 
                          if o.user_id == user.user_id 
                          and o.card_id == card_id 
                          and o.status == "pending"]
    if user_pending_orders:
        await callback.answer("❌ У вас уже есть активный заказ на эту карточку!", show_alert=True)
        return
    
    expires_at = datetime.fromisoformat(item.expires_at)
    if expires_at <= datetime.now():
        del shop_items[card_id]
        save_data()
        await callback.answer("❌ Срок действия карточки истек!", show_alert=True)
        return
    
    order = create_order(user, card_id, item.price)
    
    if not order:
        await callback.answer("❌ Не удалось создать заказ!", show_alert=True)
        return
    
    rarity_icon = get_rarity_color(card.rarity)
    
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> {rarity_icon} {card.name} ({get_rarity_name(card.rarity)})\n"
        f"💰 <b>Сумма:</b> {item.price}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order.order_id}</code>\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )
    
    await show_payment_methods(
        callback=callback,
        product_type="shop_card",
        product_id=card_id,
        price=item.price,
        description=f"{rarity_icon} {card.name} ({get_rarity_name(card.rarity)})"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🛒 <b>Новый заказ!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order.order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Карточка:</b> {card.name}\n"
                     f"💰 <b>Сумма:</b> {item.price}₽\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    await callback.answer("✅ Заказ создан!")

@dp.callback_query(lambda c: c.data == "shop_help")
async def shop_help_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    await callback.message.answer(
        "🛒 <b>Помощь по магазину</b>\n\n"
        "🎴 <b>Как работает магазин:</b>\n"
        "• Каждые 12 часов появляются новые карточки\n"
        "• Карточки имеют разные цены в зависимости от редкости\n"
        "• При нажатии на карточку создается заказ\n"
        "• Оплатите заказ и отправьте скриншот через /payment\n"
        "• Администратор подтвердит заказ в течение 24 часов\n\n"
        
        "💰 <b>Цены по редкостям:</b>\n"
        f"• ⚪️ Обычная: {SHOP_PRICES['basic']}₽\n"
        f"• 🔵 Крутая: {SHOP_PRICES['cool']}₽\n"
        f"• 🟡 Легендарная: {SHOP_PRICES['legendary']}₽\n"
        f"• 🟣 Виниловая фигурка: {SHOP_PRICES['vinyl figure']}₽\n\n"
        
        "⏰ <b>Время обновления:</b>\n"
        "• Магазин обновляется каждые 12 часов\n"
        "• Используйте кнопку '🔄 Обновить' для проверки новых карточек\n"
        "• Карточки могут закончиться, если их купили другие игроки\n\n"
        
        "💵 <b>Процесс покупки:</b>\n"
        "1. Выберите карточку в магазине\n"
        "2. Выберите способ оплаты\n"
        "3. Оплатите по выбранному способу\n"
        "4. Используйте команду /payment чтобы отправить скриншот\n"
        "5. Ожидайте подтверждения администратора\n"
        "6. Получите карточку в инвентарь\n\n"
        
        "❓ <b>Частые вопросы:</b>\n"
        "• Q: Карточка пропала после обновления?\n"
        "• A: Да, каждая карточка доступна 12 часов\n"
        "• Q: Можно ли вернуть карточку?\n"
        "• A: Нет, покупки невозвратные\n"
        "• Q: Почему разные цены?\n"
        "• A: Цена зависит от редкости карточки"
    )
    await callback.answer()

@dp.message(F.text == "🎪 Эксклюзивы")
async def exclusive_shop_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к эксклюзивам необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    active_exclusives = [ec for ec in exclusive_cards.values() if ec.can_purchase()]
    
    if not active_exclusives:
        await message.answer(
            "🎪 <b>Эксклюзивные карточки</b>\n\n"
            "Сейчас нет доступных эксклюзивных карточек.\n"
            "Следите за новыми поступлениями!"
        )
        return
    
    keyboard = InlineKeyboardBuilder()
    
    for exclusive in active_exclusives[:10]:
        card = cards.get(exclusive.card_id)
        if card:
            remaining = exclusive.total_copies - exclusive.sold_copies
            
            keyboard.add(InlineKeyboardButton(
                text=f"🎴 {card.name} - {exclusive.price}₽ ({remaining}/{exclusive.total_copies})",
                callback_data=f"buy_exclusive_{exclusive.card_id}"
            ))
    
    keyboard.adjust(1)
    
    response = "🎪 <b>ЭКСКЛЮЗИВНЫЕ КАРТОЧКИ</b>\n\n"
    response += "🔥 <b>Только здесь! Только сейчас!</b>\n"
    response += "Эти карточки можно получить ТОЛЬКО покупкой.\n"
    response += "Они никогда не выпадают из обычных наборов.\n\n"
    response += "<b>Доступные эксклюзивы:</b>\n"
    
    await message.answer(response, reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("buy_exclusive_"))
async def buy_exclusive_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    card_id = callback.data.replace("buy_exclusive_", "")
    
    if card_id not in exclusive_cards:
        await callback.answer("❌ Карточка не найдена!", show_alert=True)
        return
    
    exclusive = exclusive_cards[card_id]
    card = cards.get(card_id)
    
    if not card:
        await callback.answer("❌ Карточка не найдена!", show_alert=True)
        return
    
    if not exclusive.can_purchase():
        await callback.answer("❌ Карточка больше не доступна!", show_alert=True)
        return
    
    user = get_or_create_user(callback.from_user.id)
    
    order_id = f"exclusive_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    
    order = Order(order_id, user.user_id, card_id, exclusive.price)
    orders[order_id] = order
    save_data()
    
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> 🎴 {card.name} (ЭКСКЛЮЗИВ)\n"
        f"💰 <b>Сумма:</b> {exclusive.price}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n"
        f"📦 <b>Осталось копий:</b> {exclusive.total_copies - exclusive.sold_copies}/{exclusive.total_copies}\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )
    
    await show_payment_methods(
        callback=callback,
        product_type="exclusive_card",
        product_id=card_id,
        price=exclusive.price,
        description=f"🎴 {card.name} (ЭКСКЛЮЗИВ)"
    )
    
    await callback.answer("✅ Заказ создан!")

@dp.message(F.text == "🎴 Инвентарь")
async def inventory_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к инвентарю необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    user = get_or_create_user(
        message.from_user.id, 
        message.from_user.username,
        message.from_user.first_name
    )
    
    if not user.cards:
        await message.answer("📭 <b>Ваш инвентарь пуст!</b>\n\nНапишите <b>фанко</b> в групповом чате с ботом чтобы получить первую карточку.")
        return
    
    user_inventory_pages[message.from_user.id] = {
        'current_page': 0,
        'cards': list(user.cards.items())
    }
    
    await show_inventory_page(message.from_user.id, message.chat.id)

async def show_inventory_page(user_id: int, chat_id: int):
    if user_id not in user_inventory_pages:
        return
    
    data = user_inventory_pages[user_id]
    cards_list = data['cards']
    current_page = data['current_page']
    cards_per_page = 10
    
    total_pages = (len(cards_list) + cards_per_page - 1) // cards_per_page
    start_idx = current_page * cards_per_page
    end_idx = min(start_idx + cards_per_page, len(cards_list))
    
    keyboard = InlineKeyboardBuilder()
    
    for card_id, quantity in cards_list[start_idx:end_idx]:
        card = cards.get(card_id)
        if card:
            rarity_icon = get_rarity_color(card.rarity)
            keyboard.add(InlineKeyboardButton(
                text=f"{rarity_icon} {card.name} (x{quantity})",
                callback_data=f"view_card_{card_id}"
            ))
    
    keyboard.adjust(1)
    
    pagination_row = []
    if current_page > 0:
        pagination_row.append(InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data=f"inventory_page_{current_page - 1}"
        ))
    
    if current_page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton(
            text="Вперед ▶️", 
            callback_data=f"inventory_page_{current_page + 1}"
        ))
    
    if pagination_row:
        keyboard.row(*pagination_row)
    
    keyboard.row(InlineKeyboardButton(
        text="🔙 Назад в меню", 
        callback_data="back_to_menu"
    ))
    
    await bot.send_message(
        chat_id,
        f"🎴 <b>Ваш инвентарь</b>\n\n"
        f"📊 Страница {current_page + 1} из {total_pages}\n"
        f"📚 Всего карточек: {sum(q for _, q in cards_list)}\n"
        f"⭐ Уникальных: {len(cards_list)}",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("inventory_page_"))
async def inventory_page_handler(callback: types.CallbackQuery):
    page_num = int(callback.data.replace("inventory_page_", ""))
    user_id = callback.from_user.id
    
    if user_id in user_inventory_pages:
        user_inventory_pages[user_id]['current_page'] = page_num
        await callback.message.delete()
        await show_inventory_page(user_id, callback.message.chat.id)
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_card_"))
async def view_card_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("view_card_", "")
    card = cards.get(card_id)
    
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return
    
    user = get_or_create_user(callback.from_user.id)
    quantity = user.cards.get(card_id, 0)
    
    rarity_icon = get_rarity_color(card.rarity)
    rarity_name = get_rarity_name(card.rarity)
    
    response = f"{rarity_icon} <b>{card.name}</b>\n\n"
    response += f"📊 <b>Редкость:</b> {rarity_name}\n"
    response += f"📈 <b>Количество:</b> {quantity} шт.\n"
    response += f"🆔 <b>ID:</b> {card_id}"
    
    image_path = get_image_path(card)
    if image_path and os.path.exists(image_path):
        try:
            await callback.message.answer_photo(
                photo=FSInputFile(image_path),
                caption=response
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await callback.message.answer(response)
    else:
        await callback.message.answer(response)
    
    await callback.answer()

@dp.message(F.text == "🔄 Обмен")
async def trade_menu_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к обменам необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    user = get_or_create_user(message.from_user.id)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="📝 Создать предложение", 
        callback_data="create_trade"
    ))
    keyboard.add(InlineKeyboardButton(
        text="📨 Мои предложения", 
        callback_data="my_trades"
    ))
    keyboard.add(InlineKeyboardButton(
        text="📥 Входящие предложения", 
        callback_data="incoming_trades"
    ))
    keyboard.add(InlineKeyboardButton(
        text="❓ Как работает обмен", 
        callback_data="trade_help"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="back_to_menu"
    ))
    keyboard.adjust(2)
    
    await message.answer(
        "🔄 <b>Система обмена карточками</b>\n\n"
        "Здесь вы можете обмениваться карточками с другими пользователями.\n\n"
        "📝 <b>Создать предложение</b> - предложить обмен другому пользователю\n"
        "📨 <b>Мои предложения</b> - созданные вами предложения\n"
        "📥 <b>Входящие предложения</b> - предложения от других пользователей\n\n"
        "⏰ <b>Кулдаун обменов:</b> 4 часа (2 часа с премиумом)\n"
        "📈 <b>Статус:</b> " + ("✅ Можно обмениваться" if can_trade(user)[0] else f"⏰ Ждать: {can_trade(user)[1]}"),
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "create_trade")
async def create_trade_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    user = get_or_create_user(callback.from_user.id)
    
    can_trade_now, remaining = can_trade(user)
    if not can_trade_now:
        await callback.answer(f"⏰ Вы можете создать обмен через {remaining}", show_alert=True)
        return
    
    if not user.cards:
        await callback.answer("🎴 У вас нет карточек для обмена!", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 <b>Создание обмена</b>\n\n"
        "Введите username пользователя, которому хотите предложить обмен (начиная с @):\n"
        "<i>Пример: @username</i>"
    )
    await state.set_state(TradeStates.selecting_partner)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "my_trades")
async def my_trades_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    user_id = callback.from_user.id
    user_trades = [t for t_id, t in trades.items() 
                  if t['from_user'] == user_id and t['status'] == 'pending']
    
    if not user_trades:
        await callback.message.answer(
            "📨 <b>Мои предложения обмена</b>\n\n"
            "У вас нет активных предложений обмена."
        )
        await callback.answer()
        return
    
    response = "📨 <b>Ваши активные предложения:</b>\n\n"
    
    for trade in user_trades[:5]:
        to_user = get_or_create_user(trade['to_user'])
        response += f"🔄 <b>Обмен #{trade['id'].split('_')[1]}</b>\n"
        response += f"👤 Кому: @{to_user.username}\n"
        response += f"🎴 Карточек: {len(trade['cards'])}\n"
        response += f"📅 Создан: {datetime.fromisoformat(trade['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "incoming_trades")
async def incoming_trades_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    user_id = callback.from_user.id
    incoming_trades = [t for t_id, t in trades.items() 
                      if t['to_user'] == user_id and t['status'] == 'pending']
    
    if not incoming_trades:
        await callback.message.answer(
            "📥 <b>Входящие предложения</b>\n\n"
            "У вас нет входящих предложений обмена."
        )
        await callback.answer()
        return
    
    response = "📥 <b>Входящие предложения обмена:</b>\n\n"
    keyboard = InlineKeyboardBuilder()
    
    for trade in incoming_trades[:5]:
        from_user = get_or_create_user(trade['from_user'])
        response += f"🔄 <b>Обмен #{trade['id'].split('_')[1]}</b>\n"
        response += f"👤 От: @{from_user.username}\n"
        response += f"🎴 Карточек предлагает: {len(trade['cards'])}\n\n"
        
        keyboard.add(InlineKeyboardButton(
            text=f"👀 Просмотреть обмен #{trade['id'].split('_')[1]}",
            callback_data=f"view_trade_{trade['id']}"
        ))
    
    keyboard.adjust(1)
    keyboard.row(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="back_to_menu"
    ))
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "trade_help")
async def trade_help_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    
    await callback.message.answer(
        "❓ <b>Как работает система обмена</b>\n\n"
        "1. <b>Создание обмена:</b>\n"
        "• Выберите карточки которые хотите отдать\n"
        "• Введите username получателя (@username)\n"
        "• Ожидайте подтверждения\n\n"
        "2. <b>Принятие обмена:</b>\n"
        "• Просмотрите входящие предложения\n"
        "• Выберите карточку которую хотите получить взамен\n"
        "• Подтвердите обмен\n\n"
        "3. <b>Кулдаун:</b>\n"
        "• Между обменами: 4 часа\n"
        "• С премиумом: 2 часа\n\n"
        "4. <b>Важно:</b>\n"
        "• Обмен можно отклонить\n"
        "• Карточки возвращаются при отмене\n"
        "• Все действия логируются"
    )
    await callback.answer()

@dp.message(F.text == "❓ Помощь")
async def help_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к справке необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    await message.answer(
        "❓ <b>Помощь и инструкции</b>\n\n"
        "🎴 <b>Как получить карточку:</b>\n"
        "1. Добавьте бота в групповой чат\n"
        "2. Дайте боту права администратора\n"
        "3. Напишите слово <b>фанко</b> в чате\n"
        "4. Получите случайную карточку!\n\n"
        
        "🛒 <b>Магазин:</b>\n"
        "• Новые карточки каждые 12 часов\n"
        "• Цены зависят от редкости\n"
        "• Для покупки создается заказ, нужно отправить скриншот оплаты\n"
        "• Используйте /payment для отправки скриншота\n\n"
        
        "🔄 <b>Обмен:</b>\n"
        "• Обменивайтесь карточками с другими\n"
        "• Кулдаун обменов: 4 часа (2 с премиумом)\n"
        "• Создавайте и принимайте предложения\n\n"
        
        "💎 <b>Премиум и покупки:</b>\n"
        "• Премиум: удвоенный шанс на редкие карты + ежедневный бонус\n"
        "• Уменьшенный кулдаун: открывайте карточки каждые 2 часа\n"
        "• Подробнее: нажмите '💝 Поддержать проект'\n\n"
        
        "📞 <b>Поддержка:</b>\n"
        "• Связь с автором: @prikolovwork\n"
        "• Канал: @funkopopcards\n"
        "• Пожертвования: https://tbank.ru/cf/17LdZPej2CV\n\n"
        "<i>Используйте кнопки меню для навигации</i>"
    )

@dp.message(F.text == "💰 Топ покупателей")
async def top_spenders_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к топам необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    top_daily = get_top_spenders(1, 10)
    top_monthly = get_top_spenders(30, 10)
    top_all_time = get_top_spenders(365*10, 10)
    
    response = "💰 <b>ТОП ПОКУПАТЕЛЕЙ</b>\n\n"
    
    response += "📅 <b>ЗА СЕГОДНЯ:</b>\n"
    for i, spender in enumerate(top_daily[:3], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
        response += f"{medal} @{spender['user'].username}: {spender['total_spent']}₽\n"
    
    response += "\n📅 <b>ЗА МЕСЯЦ:</b>\n"
    for i, spender in enumerate(top_monthly[:5], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        response += f"{medal} @{spender['user'].username}: {spender['total_spent']}₽ ({spender['orders_count']} зак.)\n"
    
    current_user = get_or_create_user(message.from_user.id)
    user_position = None
    user_total = 0
    
    for idx, spender in enumerate(top_monthly, 1):
        if spender['user'].user_id == current_user.user_id:
            user_position = idx
            user_total = spender['total_spent']
            break
    
    if user_position:
        response += f"\n👤 <b>Ваше место в месячном топе:</b> {user_position}\n"
        response += f"💰 Потрачено за месяц: {user_total}₽\n"
        
        if user_position > 1 and len(top_monthly) >= user_position - 1:
            next_up = top_monthly[user_position - 2]
            needed = next_up['total_spent'] - user_total + 1
            response += f"📈 До {user_position-1} места: {needed}₽\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="top_spenders"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_tops"))
    keyboard.adjust(2)
    
    await message.answer(response, reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data == "top_spenders")
async def refresh_top_spenders(callback: types.CallbackQuery):
    await top_spenders_menu(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_tops")
async def back_to_tops_handler(callback: types.CallbackQuery):
    await top_players_menu(callback.message)
    await callback.answer()

def get_top_by_collection_percentage(limit=10):
    if not cards:
        return []
    
    total_cards = len(cards)
    user_stats = []
    
    for user in users.values():
        if user.is_banned or user.is_frozen:
            continue
            
        unique_cards = len(user.cards)
        if total_cards > 0:
            percentage = (unique_cards / total_cards) * 100
        else:
            percentage = 0
            
        user_stats.append({
            'user': user,
            'percentage': percentage,
            'unique_cards': unique_cards,
            'total_cards': sum(user.cards.values())
        })
    
    user_stats.sort(key=lambda x: x['percentage'], reverse=True)
    return user_stats[:limit]

def get_top_by_unique_cards(limit=10):
    user_stats = []
    
    for user in users.values():
        if user.is_banned or user.is_frozen:
            continue
            
        unique_cards = len(user.cards)
        total_cards = sum(user.cards.values())
        
        user_stats.append({
            'user': user,
            'unique_cards': unique_cards,
            'total_cards': total_cards
        })
    
    user_stats.sort(key=lambda x: x['unique_cards'], reverse=True)
    return user_stats[:limit]

def get_top_by_total_cards(limit=10):
    user_stats = []
    
    for user in users.values():
        if user.is_banned or user.is_frozen:
            continue
            
        total_cards = sum(user.cards.values())
        unique_cards = len(user.cards)
        
        user_stats.append({
            'user': user,
            'total_cards': total_cards,
            'unique_cards': unique_cards
        })
    
    user_stats.sort(key=lambda x: x['total_cards'], reverse=True)
    return user_stats[:limit]

@dp.message(F.text == "🏆 Топ игроков")
async def top_players_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"❌ <b>Для доступа к топам необходимо подписаться на канал:</b>\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите /start"
        )
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Топ по % коллекции", callback_data="top_collection_percentage"))
    keyboard.add(InlineKeyboardButton(text="⭐ Топ по уникальным карточкам", callback_data="top_unique_cards"))
    keyboard.add(InlineKeyboardButton(text="🎴 Топ по общему количеству", callback_data="top_total_cards"))
    keyboard.add(InlineKeyboardButton(text="💰 Топ покупателей", callback_data="top_spenders_btn"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    keyboard.adjust(1)
    
    total_players = len([u for u in users.values() if not u.is_banned and not u.is_frozen])
    
    await message.answer(
        f"🏆 <b>Топ игроков</b>\n\n"
        f"📈 Всего игроков: {total_players}\n"
        f"🎴 Всего карточек: {len(cards)}\n\n"
        f"<b>Категории:</b>\n"
        f"1. 📊 Топ по % коллекции\n"
        f"2. ⭐ Топ по уникальным карточкам\n"
        f"3. 🎴 Топ по общему количеству\n"
        f"4. 💰 Топ покупателей\n\n"
        f"Выберите:",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "top_spenders_btn")
async def top_spenders_btn_handler(callback: types.CallbackQuery):
    await top_spenders_menu(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "top_collection_percentage")
async def top_collection_percentage_handler(callback: types.CallbackQuery):
    top_players = get_top_by_collection_percentage(limit=10)
    
    if not top_players:
        await callback.answer("Нет данных", show_alert=True)
        return
    
    response = "📊 <b>Топ по проценту коллекции</b>\n\n"
    
    for i, stats in enumerate(top_players, 1):
        user = stats['user']
        percentage = stats['percentage']
        medal = ""
        if i == 1: medal = "🥇 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "
        
        response += f"{medal}<b>{i}. @{user.username or 'без username'}</b>\n"
        response += f"   📈 {percentage:.1f}%\n\n"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "top_unique_cards")
async def top_unique_cards_handler(callback: types.CallbackQuery):
    top_players = get_top_by_unique_cards(limit=10)
    
    if not top_players:
        await callback.answer("Нет данных", show_alert=True)
        return
    
    response = "⭐ <b>Топ по уникальным карточкам</b>\n\n"
    
    for i, stats in enumerate(top_players, 1):
        user = stats['user']
        medal = ""
        if i == 1: medal = "🥇 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "
        
        response += f"{medal}<b>{i}. @{user.username or 'без username'}</b>\n"
        response += f"   ⭐ {stats['unique_cards']} карточек\n\n"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "top_total_cards")
async def top_total_cards_handler(callback: types.CallbackQuery):
    top_players = get_top_by_total_cards(limit=10)
    
    if not top_players:
        await callback.answer("Нет данных", show_alert=True)
        return
    
    response = "🎴 <b>Топ по общему количеству карточек</b>\n\n"
    
    for i, stats in enumerate(top_players, 1):
        user = stats['user']
        medal = ""
        if i == 1: medal = "🥇 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "
        
        response += f"{medal}<b>{i}. @{user.username or 'без username'}</b>\n"
        response += f"   🎴 {stats['total_cards']} карточек\n\n"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.message(Command("topreferrals"))
async def top_referrals_command(message: types.Message):
    """Топ пользователей по приглашениям"""
    if not await check_access_before_handle(message, message.from_user.id):
        return
    
    # Сортируем пользователей по количеству рефералов
    users_with_referrals = []
    for user in users.values():
        if user.referrals:
            # Считаем только активных рефералов (были онлайн за последнюю неделю)
            active_referrals = 0
            for ref_id in user.referrals:
                ref_user = users.get(ref_id)
                if ref_user:
                    last_seen = datetime.fromisoformat(ref_user.last_seen)
                    if (datetime.now() - last_seen).days < 7:
                        active_referrals += 1
            
            users_with_referrals.append({
                'user': user,
                'total': len(user.referrals),
                'active': active_referrals,
                'cards': len(user.referrals) // 3
            })
    
    if not users_with_referrals:
        await message.answer("📊 <b>Топ по приглашениям</b>\n\nПока никто не пригласил друзей.")
        return
    
    # Сортируем по количеству рефералов
    users_with_referrals.sort(key=lambda x: x['total'], reverse=True)
    
    response = "🏆 <b>ТОП ПРИГЛАШАЛОВ</b>\n\n"
    
    for i, data in enumerate(users_with_referrals[:10], 1):
        user = data['user']
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        
        response += f"{medal} <b>@{user.username or 'без username'}</b>\n"
        response += f"   👥 Приглашено: {data['total']} (🟢 {data['active']} активных)\n"
        response += f"   🎴 Карточек получено: {data['cards']}\n"
        response += f"   ⭐ Уровень: {user.level}\n\n"
    
    # Показываем позицию текущего пользователя
    current_user = get_or_create_user(message.from_user.id)
    current_position = None
    
    for idx, data in enumerate(users_with_referrals, 1):
        if data['user'].user_id == current_user.user_id:
            current_position = idx
            break
    
    if current_position:
        response += f"👤 <b>Ваша позиция:</b> {current_position}\n"
        response += f"👥 Ваших рефералов: {len(current_user.referrals)}\n"
        
        if current_position > 1 and len(users_with_referrals) >= current_position - 1:
            next_up = users_with_referrals[current_position - 2]
            needed = next_up['total'] - len(current_user.referrals) + 1
            response += f"📈 До {current_position-1} места: {needed} приглашений\n"
    
    response += f"\n📢 <b>Как приглашать:</b>\nИспользуйте команду /invite чтобы получить свою ссылку!"
    
    await message.answer(response)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ <b>У вас нет доступа к админ-панели.</b>")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="➕ Добавить карточку", callback_data="admin_add_card"))
    keyboard.add(InlineKeyboardButton(text="🗑️ Удалить карточку", callback_data="admin_delete_card"))
    keyboard.add(InlineKeyboardButton(text="💎 Выдать премиум", callback_data="admin_give_premium"))
    keyboard.add(InlineKeyboardButton(text="⚡ Сбросить кулдаун", callback_data="admin_reset_cooldown"))
    keyboard.add(InlineKeyboardButton(text="⏰ Добавить кулдаун", callback_data="admin_add_cooldown"))
    keyboard.add(InlineKeyboardButton(text="⚡ Выдать уменьш. кулдаун", callback_data="admin_give_reduced_cd"))
    keyboard.add(InlineKeyboardButton(text="🔄 Выдать уменьш. кулдаун обменов", callback_data="admin_give_reduced_trade_cd"))
    keyboard.add(InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders"))
    keyboard.add(InlineKeyboardButton(text="⛔ Забанить пользователя", callback_data="admin_ban_user"))
    keyboard.add(InlineKeyboardButton(text="✅ Разбанить пользователя", callback_data="admin_unban_user"))
    keyboard.add(InlineKeyboardButton(text="❄️ Заморозить аккаунт", callback_data="admin_freeze_user"))
    keyboard.add(InlineKeyboardButton(text="☀️ Разморозить аккаунт", callback_data="admin_unfreeze_user"))
    keyboard.add(InlineKeyboardButton(text="⚙️ Система уровней", callback_data="admin_level_system"))
    keyboard.add(InlineKeyboardButton(text="📥 База данных", callback_data="admin_database"))
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить пул", callback_data="admin_update_pool"))
    keyboard.add(InlineKeyboardButton(text="🔄 Перезапуск бота", callback_data="admin_restart"))
    keyboard.adjust(2, 2, 2, 2, 2, 2, 2, 1)
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите сообщение для рассылки всем пользователям:"
    )
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    text = message.text
    sent = 0
    failed = 0
    
    await message.answer(f"📤 <b>Начинаю рассылку...</b>\n\nСообщение:\n{text}")
    
    for user_id, user in users.items():
        try:
            await bot.send_message(user_id, f"📢 <b>Объявление от администрации:</b>\n\n{text}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
    
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {sent} пользователям\n"
        f"❌ Не отправлено: {failed} пользователям\n\n"
        f"Всего пользователей: {len(users)}"
    )
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    total_users = len(users)
    active_today = 0
    total_cards = sum(sum(user.cards.values()) for user in users.values())
    premium_users = sum(1 for user in users.values() if user.is_premium)
    
    today = datetime.now().date()
    for user in users.values():
        if user.last_seen:
            last_seen = datetime.fromisoformat(user.last_seen).date()
            if last_seen == today:
                active_today += 1
    
    total_orders = len(orders)
    pending_orders = len([o for o in orders.values() if o.status == "pending"])
    confirmed_orders = len([o for o in orders.values() if o.status == "confirmed"])
    rejected_orders = len([o for o in orders.values() if o.status == "rejected"])
    
    if LEVEL_SETTINGS['enabled']:
        avg_level = sum(u.level for u in users.values()) / total_users if total_users > 0 else 0
        max_level = max((u.level for u in users.values()), default=0)
        level_10_plus = len([u for u in users.values() if u.level >= 10])
    else:
        avg_level = max_level = level_10_plus = 0
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👤 Всего пользователей: {total_users}\n"
        f"📅 Активных сегодня: {active_today}\n"
        f"🎴 Всего карточек выдано: {total_cards}\n"
        f"💎 Премиум пользователей: {premium_users}\n"
        f"📈 Уникальных карточек: {len(cards)}\n"
        f"🔄 Активных обменов: {len([t for t in trades.values() if t['status'] == 'pending'])}\n"
        f"🛒 Карточек в магазине: {len(shop_items)}\n"
        f"🎪 Эксклюзивных карточек: {len(exclusive_cards)}\n"
        f"📋 Всего заказов: {total_orders}\n"
        f"⏳ Ожидают оплаты: {pending_orders}\n"
        f"✅ Подтверждено: {confirmed_orders}\n"
        f"❌ Отклонено: {rejected_orders}\n"
    )
    
    if LEVEL_SETTINGS['enabled']:
        stats_text += f"🎮 Средний уровень: {avg_level:.1f}\n"
        stats_text += f"🏆 Максимальный уровень: {max_level}\n"
        stats_text += f"⭐ Игроков 10+ уровня: {level_10_plus}\n\n"
    else:
        stats_text += "\n"
    
    stats_text += f"<b>Последние 5 пользователей:</b>\n"
    
    sorted_users = sorted(users.values(), 
                         key=lambda u: datetime.fromisoformat(u.created_at), 
                         reverse=True)
    
    for i, user in enumerate(sorted_users[:5], 1):
        created = datetime.fromisoformat(user.created_at).strftime('%d.%m.%Y')
        stats_text += f"{i}. @{user.username} ({created}) - {len(user.cards)} карт"
        if LEVEL_SETTINGS['enabled']:
            stats_text += f", уровень {user.level}"
        stats_text += "\n"
    
    await callback.message.answer(stats_text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_add_card")
async def admin_add_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ <b>Добавление новой карточки</b>\n\n"
        "Введите название карточки:"
    )
    await state.set_state(AdminStates.waiting_for_card_name)
    await callback.answer()

@dp.message(AdminStates.waiting_for_card_name)
async def process_card_name(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        await state.clear()
        return
    
    await state.update_data(card_name=message.text)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⚪️ Обычная", callback_data="rarity_basic"))
    keyboard.add(InlineKeyboardButton(text="🔵 Крутая", callback_data="rarity_cool"))
    keyboard.add(InlineKeyboardButton(text="🟡 Легендарная", callback_data="rarity_legendary"))
    keyboard.add(InlineKeyboardButton(text="🟣 Виниловая фигурка", callback_data="rarity_vinyl"))
    keyboard.adjust(2)
    
    await message.answer(
        f"📝 Название карточки: <b>{message.text}</b>\n\n"
        "Теперь выберите редкость карточки:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(AdminStates.waiting_for_card_rarity)

@dp.callback_query(lambda c: c.data.startswith("rarity_"))
async def process_card_rarity(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        await state.clear()
        return
    
    rarity = callback.data.replace("rarity_", "")
    rarity_names = {
        "basic": "Обычная",
        "cool": "Крутая", 
        "legendary": "Легендарная",
        "vinyl": "Виниловая фигурка"
    }
    
    await state.update_data(card_rarity=rarity)
    
    data = await state.get_data()
    card_name = data.get('card_name', 'Неизвестно')
    
    await callback.message.edit_text(
        f"📝 <b>Добавление карточки</b>\n\n"
        f"Название: <b>{card_name}</b>\n"
        f"Редкость: <b>{rarity_names.get(rarity, rarity)}</b>\n\n"
        "Теперь отправьте изображение карточки (фото) или нажмите 'Пропустить' чтобы добавить без изображения."
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🖼️ Отправить изображение", callback_data="send_image"))
    keyboard.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_image"))
    keyboard.adjust(1)
    
    await callback.message.answer("Выберите действие:", reply_markup=keyboard.as_markup())
    await state.set_state(AdminStates.waiting_for_card_image)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "send_image", AdminStates.waiting_for_card_image)
async def ask_for_card_image(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📷 Отправьте изображение карточки (фото):")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "skip_image", AdminStates.waiting_for_card_image)
async def skip_card_image(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await complete_card_add(callback, state, data, image_filename="")
    await callback.answer()

@dp.message(AdminStates.waiting_for_card_image, F.photo)
async def process_card_image_with_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1]
        photo_file = await bot.get_file(photo.file_id)
        
        data = await state.get_data()
        card_id = f"card_{int(datetime.now().timestamp())}"
        
        photo_path = IMAGES_DIR / f"{card_id}.jpg"
        await bot.download_file(photo_file.file_path, photo_path)
        
        image_filename = f"{card_id}.jpg"
        await complete_card_add(message, state, data, image_filename)
        
    except Exception as e:
        logger.error(f"Ошибка сохранения изображения: {e}")
        await message.answer("❌ Ошибка сохранения изображения. Карточка добавлена без изображения.")
        await complete_card_add(message, state, data, image_filename="")

async def complete_card_add(source, state: FSMContext, data: dict, image_filename: str):
    card_name = data.get('card_name')
    card_rarity = data.get('card_rarity')
    
    card_id = f"card_{int(datetime.now().timestamp())}"
    
    cards[card_id] = Card(
        card_id=card_id,
        name=card_name,
        rarity=card_rarity,
        image_filename=image_filename
    )
    
    update_card_pool()
    save_data()
    
    if isinstance(source, types.CallbackQuery):
        await source.message.answer(
            f"✅ <b>Карточка добавлена успешно!</b>\n\n"
            f"🎴 Название: <b>{card_name}</b>\n"
            f"📊 Редкость: <b>{get_rarity_name(card_rarity)}</b>\n"
            f"🆔 ID: <code>{card_id}</code>\n"
            f"🖼️ Изображение: {'✅ Есть' if image_filename else '❌ Нет'}\n\n"
            f"Всего карточек в системе: {len(cards)}"
        )
    elif isinstance(source, types.Message):
        await source.answer(
            f"✅ <b>Карточка добавлена успешно!</b>\n\n"
            f"🎴 Название: <b>{card_name}</b>\n"
            f"📊 Редкость: <b>{get_rarity_name(card.rarity)}</b>\n"
            f"🆔 ID: <code>{card_id}</code>\n"
            f"🖼️ Изображение: {'✅ Есть' if image_filename else '❌ Нет'}\n\n"
            f"Всего карточек в системе: {len(cards)}"
        )
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_delete_card")
async def admin_delete_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if not cards:
        await callback.message.answer("❌ В системе нет карточек для удаления.")
        await callback.answer()
        return
    
    cards_list = "\n".join([f"{card_id}: {card.name} ({card.rarity})" 
                           for card_id, card in cards.items()])
    
    await callback.message.answer(
        f"🗑️ <b>Удаление карточки</b>\n\n"
        f"Доступные карточки:\n{cards_list}\n\n"
        "Введите ID карточки для удаления:"
    )
    await state.set_state(AdminStates.waiting_for_card_id_to_delete)
    await callback.answer()

@dp.message(AdminStates.waiting_for_card_id_to_delete)
async def process_card_id_to_delete(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    card_id = message.text.strip()
    
    if card_id not in cards:
        await message.answer(f"❌ Карточка с ID '{card_id}' не найдена.")
        await state.clear()
        return
    
    card = cards[card_id]
    
    if card.image_filename:
        image_path = IMAGES_DIR / card.image_filename
        if image_path.exists():
            try:
                os.remove(image_path)
            except:
                pass
    
    del cards[card_id]
    
    update_card_pool()
    save_data()
    
    await message.answer(
        f"✅ <b>Карточка удалена успешно!</b>\n\n"
        f"🎴 Название: <b>{card.name}</b>\n"
        f"📊 Редкость: <b>{get_rarity_name(card.rarity)}</b>\n"
        f"🆔 ID: <code>{card_id}</code>\n\n"
        f"Всего карточек в системе: {len(cards)}"
    )
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_give_premium")
async def admin_give_premium_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "💎 <b>Выдача премиум статуса</b>\n\n"
        "Введите username пользователя (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_premium_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_premium_username)
async def process_premium_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    add_premium(user, days=30)
    
    await message.answer(
        f"✅ <b>Премиум статус выдан!</b>\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"💎 Срок: 30 дней\n"
        f"🎁 Бонус: 10 карточек\n\n"
        f"Теперь пользователь получает:\n"
        f"• Удвоенный шанс на редкие карты\n"
        f"• Ежедневный бонус: 3 карточки\n"
        f"• Специальный статус в профиле"
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "🎉 <b>Вам выдан премиум статус на 30 дней!</b>\n\n"
            "💎 <b>Преимущества премиума:</b>\n"
            "• Удвоенный шанс на редкие карты\n"
            "• Ежедневный бонус: 3 карточки\n"
            "• Специальный статус в профиле\n"
            "• 10 карточек в подарок!\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_reset_cooldown")
async def admin_reset_cooldown_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "⚡ <b>Сброс кулдауна</b>\n\n"
        "Введите username пользователя (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_cooldown_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_cooldown_username)
async def process_cooldown_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    user.last_card_time = None
    user.last_trade_time = None
    update_user_interaction(user)
    
    await message.answer(
        f"✅ <b>Кулдаун сброшен!</b>\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"⚡ Кулдаун карточек: сброшен\n"
        f"🔄 Кулдаун обменов: сброшен\n\n"
        f"Пользователь может сразу открывать карточки и совершать обмены."
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "⚡ <b>Ваши кулдауны сброшены администратором!</b>\n\n"
            "Теперь вы можете:\n"
            "• Открывать карточки сразу\n"
            "• Совершать обмены без ожидания\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_cooldown")
async def admin_add_cooldown_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "⏰ <b>Добавление кулдауна</b>\n\n"
        "Введите username пользователя (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_add_cooldown_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_add_cooldown_username)
async def process_add_cooldown_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    user.last_card_time = datetime.now().isoformat()
    update_user_interaction(user)
    
    await message.answer(
        f"✅ <b>Кулдаун добавлен!</b>\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"⏰ Кулдаун карточек: 4 часа\n"
        f"📅 Установлен: сейчас\n\n"
        f"Пользователь сможет открывать карточки через 4 часа."
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "⏰ <b>Вам добавлен кулдаун карточек!</b>\n\n"
            "Вы сможете открывать следующие карточки через 4 часа.\n\n"
            "Это мера применяется администратором."
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_give_reduced_cd")
async def admin_give_reduced_cd_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "⚡ <b>Выдача уменьшенного кулдауна карточек</b>\n\n"
        "Введите username пользователя (начиная с @):\n"
        "<i>Пользователь сможет открывать карточки каждые 2 часа вместо 4</i>"
    )
    await state.set_state(AdminStates.waiting_for_reduced_cd_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_reduced_cd_username)
async def process_reduced_cd_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    add_reduced_cd(user, days=30)
    
    await message.answer(
        f"✅ <b>Уменьшенный кулдаун карточек выдан!</b>\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"⚡ Эффект: Кулдаун карточек 2ч вместо 4ч\n"
        f"📅 Действует: 30 дней\n\n"
        f"Теперь пользователь может открывать карточки каждые 2 часа."
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "🎉 <b>Вам выдан уменьшенный кулдаун карточек!</b>\n\n"
            "⚡ Теперь вы можете открывать карточки каждые <b>2 часа</b> вместо 4!\n"
            "📅 Действует: <b>30 дней</b>\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_give_reduced_trade_cd")
async def admin_give_reduced_trade_cd_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "🔄 <b>Выдача уменьшенного кулдауна обменов</b>\n\n"
        "Введите username пользователя (начиная с @):\n"
        "<i>Пользователь сможет совершать обмены каждые 2 часа вместо 4</i>"
    )
    await state.set_state(AdminStates.waiting_for_reduced_trade_cd_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_reduced_trade_cd_username)
async def process_reduced_trade_cd_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    add_reduced_trade_cd(user, days=30)
    
    await message.answer(
        f"✅ <b>Уменьшенный кулдаун обменов выдан!</b>\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"🔄 Эффект: Кулдаун обменов 2ч вместо 4ч\n"
        f"📅 Действует: 30 дней\n\n"
        f"Теперь пользователь может совершать обмены каждые 2 часа."
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "🎉 <b>Вам выдан уменьшенный кулдаун обменов!</b>\n\n"
            "🔄 Теперь вы можете совершать обмены каждые <b>2 часа</b> вместо 4!\n"
            "📅 Действует: <b>30 дней</b>\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_orders")
async def admin_orders_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if not orders:
        await callback.message.answer("📋 <b>Заказы</b>\n\nНет активных заказов.")
        await callback.answer()
        return
    
    pending_orders = [o for o in orders.values() if o.status == "pending"]
    confirmed_orders = [o for o in orders.values() if o.status == "confirmed"]
    rejected_orders = [o for o in orders.values() if o.status == "rejected"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⏳ Ожидают оплаты", callback_data="admin_orders_pending"))
    keyboard.add(InlineKeyboardButton(text="✅ Подтвержденные", callback_data="admin_orders_confirmed"))
    keyboard.add(InlineKeyboardButton(text="❌ Отклоненные", callback_data="admin_orders_rejected"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика заказов", callback_data="admin_orders_stats"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="admin_back"))
    keyboard.adjust(2)
    
    await callback.message.answer(
        f"📋 <b>Управление заказами</b>\n\n"
        f"⏳ Ожидают оплаты: {len(pending_orders)}\n"
        f"✅ Подтвержденные: {len(confirmed_orders)}\n"
        f"❌ Отклоненные: {len(rejected_orders)}\n"
        f"📊 Всего заказов: {len(orders)}\n\n"
        f"Выберите категорию для просмотра:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_orders_pending")
async def admin_orders_pending_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    pending_orders = [o for o in orders.values() if o.status == "pending"]
    
    if not pending_orders:
        await callback.message.answer("⏳ <b>Заказы ожидающие оплаты</b>\n\nНет заказов ожидающих оплаты.")
        await callback.answer()
        return
    
    response = f"⏳ <b>Заказы ожидающие оплаты ({len(pending_orders)})</b>\n\n"
    keyboard = InlineKeyboardBuilder()
    
    for i, order in enumerate(pending_orders[:10], 1):
        user = users.get(order.user_id)
        card = cards.get(order.card_id)
        
        if user and card:
            created = datetime.fromisoformat(order.created_at).strftime('%d.%m %H:%M')
            response += f"{i}. <b>{order.order_id}</b>\n"
            response += f"👤 @{user.username} | 🎴 {card.name} | 💰 {order.price}₽\n"
            response += f"📅 {created}\n\n"
            
            keyboard.add(InlineKeyboardButton(
                text=f"👁️ Заказ #{order.order_id[-4:]}",
                callback_data=f"view_order_{order.order_id}"
            ))
    
    keyboard.adjust(2)
    keyboard.row(InlineKeyboardButton(
        text="🔙 Назад к заказам", 
        callback_data="admin_orders"
    ))
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_order_"))
async def view_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("view_order_", "")
    
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order = orders[order_id]
    user = users.get(order.user_id)
    card = cards.get(order.card_id)
    
    if not user or not card:
        await callback.answer("❌ Данные заказа неполные", show_alert=True)
        return
    
    created = datetime.fromisoformat(order.created_at).strftime('%d.%m.%Y %H:%M:%S')
    status_text = {
        "pending": "⏳ Ожидает оплаты",
        "confirmed": "✅ Подтвержден",
        "rejected": "❌ Отклонен"
    }.get(order.status, order.status)
    
    response = (
        f"📋 <b>Детали заказа</b>\n\n"
        f"🆔 <b>Номер:</b> {order_id}\n"
        f"👤 <b>Пользователь:</b> @{user.username} (ID: {user.user_id})\n"
        f"📧 <b>Telegram:</b> @{callback.from_user.username or 'нет username'}\n"
        f"🎴 <b>Карточка:</b> {card.name} ({get_rarity_name(card.rarity)})\n"
        f"💰 <b>Сумма:</b> {order.price}₽\n"
        f"📊 <b>Статус:</b> {status_text}\n"
        f"📅 <b>Создан:</b> {created}\n"
    )
    
    if order.confirmed_at:
        confirmed = datetime.fromisoformat(order.confirmed_at).strftime('%d.%m.%Y %H:%M:%S')
        response += f"✅ <b>Подтвержден:</b> {confirmed}\n"
        if order.admin_id:
            admin = users.get(order.admin_id)
            if admin:
                response += f"👮 <b>Администратор:</b> @{admin.username}\n"
    
    if order.payment_proof:
        response += f"\n📸 <b>Скриншот оплаты:</b> Есть ✅\n"
    else:
        response += f"\n📸 <b>Скриншот оплаты:</b> Нет ❌\n"
    
    keyboard = InlineKeyboardBuilder()
    
    if order.status == "pending":
        keyboard.add(InlineKeyboardButton(
            text="✅ Подтвердить", 
            callback_data=f"confirm_order_{order_id}"
        ))
        keyboard.add(InlineKeyboardButton(
            text="❌ Отклонить", 
            callback_data=f"reject_order_{order_id}"
        ))
        keyboard.add(InlineKeyboardButton(
            text="📸 Показать скриншот", 
            callback_data=f"show_proof_{order_id}"
        ))
    else:
        if order.status == "confirmed":
            keyboard.add(InlineKeyboardButton(
                text="📤 Сообщить пользователю", 
                callback_data=f"notify_user_{order_id}"
            ))
    
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад к заказам", 
        callback_data="admin_orders"
    ))
    keyboard.adjust(2)
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

# ================== ОБРАБОТЧИКИ ОБМЕНА ==================

@dp.callback_query(lambda c: c.data == "cancel_trade")
async def cancel_trade_handler(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания обмена"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Создание обмена отменено</b>\n\n"
        "Вы можете начать заново, нажав кнопку '📝 Создать предложение'"
    )
    await callback.answer()

@dp.message(TradeStates.selecting_partner)
async def process_trade_partner(message: types.Message, state: FSMContext):
    """Обработка username партнера для обмена"""
    username = message.text.strip().lstrip('@')
    
    # Если пользователь написал /refresh
    if username.lower() in ["/refresh", "отмена", "cancel", "stop", "стоп"]:
        await state.clear()
        await message.answer("✅ <b>Действие отменено!</b>")
        return
    
    # Находим пользователя по username
    partner = get_user_by_username(username)
    
    if not partner:
        await message.answer(f"❌ <b>Пользователь @{username} не найден!</b>")
        await state.clear()
        return
    
    # Нельзя предлагать обмен самому себе
    if partner.user_id == message.from_user.id:
        await message.answer("❌ <b>Нельзя предлагать обмен самому себе!</b>")
        await state.clear()
        return
    
    user = get_or_create_user(message.from_user.id)
    
    # Проверяем, есть ли у пользователя карточки для обмена
    if not user.cards:
        await message.answer("❌ <b>У вас нет карточек для обмена!</b>")
        await state.clear()
        return
    
    # Сохраняем данные партнера
    await state.update_data(partner_id=partner.user_id, partner_username=partner.username)
    
    # Создаем клавиатуру с карточками пользователя
    keyboard = InlineKeyboardBuilder()
    cards_data = []  # Будем хранить данные о карточках для этого пользователя
    
    for card_id, quantity in user.cards.items():
        if quantity > 0:  # Только карточки, которые есть в наличии
            card = cards.get(card_id)
            if card:
                rarity_icon = get_rarity_color(card.rarity)
                rarity_name = get_rarity_name(card.rarity)
                
                # Добавляем в клавиатуру
                keyboard.add(InlineKeyboardButton(
                    text=f"{rarity_icon} {card.name} ({rarity_name}) x{quantity}",
                    callback_data=f"select_trade_card_{card_id}"
                ))
                cards_data.append({
                    'card_id': card_id,
                    'card': card,
                    'quantity': quantity
                })
    
    if not cards_data:
        await message.answer("❌ <b>У вас нет доступных карточек для обмена!</b>")
        await state.clear()
        return
    
    keyboard.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_trade"
    ))
    keyboard.adjust(1)
    
    # Показываем первую карточку как пример
    first_card = cards_data[0]['card']
    first_card_rarity = get_rarity_name(first_card.rarity)
    first_card_icon = get_rarity_color(first_card.rarity)
    
    response = (
        f"📝 <b>Создание обмена с @{partner.username}</b>\n\n"
        f"Теперь выберите карточку, которую хотите предложить для обмена:\n\n"
        f"<b>Ваши карточки:</b> {len(cards_data)} уникальных\n\n"
        f"<i>Пример карточки:</i>\n"
        f"{first_card_icon} <b>{first_card.name}</b>\n"
        f"📊 Редкость: {first_card_rarity}\n\n"
        f"<b>Выберите карточку из списка ниже:</b>"
    )
    
    # Если у карточки есть изображение, отправляем его
    image_path = get_image_path(first_card)
    if image_path and os.path.exists(image_path):
        try:
            await message.answer_photo(
                photo=FSInputFile(image_path),
                caption=response,
                reply_markup=keyboard.as_markup()
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await message.answer(response, reply_markup=keyboard.as_markup())
    else:
        await message.answer(response, reply_markup=keyboard.as_markup())
    
    await state.update_data(cards_data=cards_data)
    await state.set_state(TradeStates.selecting_my_cards)

@dp.callback_query(lambda c: c.data.startswith("select_trade_card_"), TradeStates.selecting_my_cards)
async def select_trade_card_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора карточки для обмена"""
    card_id = callback.data.replace("select_trade_card_", "")
    
    user = get_or_create_user(callback.from_user.id)
    data = await state.get_data()
    partner_id = data.get('partner_id')
    partner_username = data.get('partner_username')
    
    if not partner_id:
        await callback.answer("❌ Ошибка: партнер не найден", show_alert=True)
        await state.clear()
        return
    
    # Проверяем, есть ли такая карточка у пользователя
    if card_id not in user.cards or user.cards[card_id] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True)
        return
    
    card = cards.get(card_id)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return
    
    # Проверяем кулдаун обменов
    can_trade_now, remaining = can_trade(user)
    if not can_trade_now:
        await callback.answer(f"⏰ Вы можете создать обмен через {remaining}", show_alert=True)
        return
    
    # Проверяем кулдаун у партнера
    partner = get_or_create_user(partner_id)
    partner_can_trade, partner_remaining = can_trade(partner)
    if not partner_can_trade:
        await callback.answer(
            f"⏰ Пользователь @{partner_username} не может принимать обмены через {partner_remaining}",
            show_alert=True
        )
        return
    
    # Создаем обмен
    cards_to_give = [card_id]
    trade_id = create_trade(callback.from_user.id, partner_id, cards_to_give)
    
    # Обновляем кулдаун обменов у отправителя
    user.last_trade_time = datetime.now().isoformat()
    update_user_interaction(user)
    save_data()
    
    # Добавляем опыт за обмен
    add_experience(user, 'trade_complete')
    
    # Получаем данные о карточке
    rarity_icon = get_rarity_color(card.rarity)
    rarity_name = get_rarity_name(card.rarity)
    
    # Создаем сообщение о создании обмена
    response = (
        f"✅ <b>Предложение обмена создано!</b>\n\n"
        f"🔄 <b>Обмен #{trade_id.split('_')[1]}</b>\n"
        f"👤 <b>Для:</b> @{partner_username}\n"
        f"🎴 <b>Вы предлагаете:</b>\n"
        f"{rarity_icon} <b>{card.name}</b>\n"
        f"📊 Редкость: {rarity_name}\n"
        f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<i>Ожидайте подтверждения от пользователя</i>"
    )
    
    # Если у карточки есть изображение, отправляем его
    image_path = get_image_path(card)
    if image_path and os.path.exists(image_path):
        try:
            await callback.message.answer_photo(
                photo=FSInputFile(image_path),
                caption=response
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await callback.message.answer(response)
    else:
        await callback.message.answer(response)
    
    # Уведомляем получателя с изображением карточки
    try:
        partner_response = (
            f"📥 <b>Новое предложение обмена!</b>\n\n"
            f"🔄 <b>Обмен #{trade_id.split('_')[1]}</b>\n"
            f"👤 <b>От:</b> @{user.username or 'пользователь'}\n"
            f"🎴 <b>Предлагает:</b>\n"
            f"{rarity_icon} <b>{card.name}</b>\n"
            f"📊 Редкость: {rarity_name}\n\n"
            f"Для принятия перейдите в 🔄 Обмен → 📥 Входящие предложения"
        )
        
        if image_path and os.path.exists(image_path):
            await bot.send_photo(
                partner_id,
                photo=FSInputFile(image_path),
                caption=partner_response
            )
        else:
            await bot.send_message(partner_id, partner_response)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления партнеру: {e}")
    
    await state.clear()
    await callback.answer(f"Вы выбрали: {card.name}")

@dp.callback_query(lambda c: c.data.startswith("show_proof_"))
async def show_proof_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("show_proof_", "")
    
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order = orders[order_id]
    
    if not order.payment_proof:
        await callback.answer("❌ Скриншот не загружен", show_alert=True)
        return
    
    try:
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=order.payment_proof,
            caption=f"📸 <b>Скриншот оплаты для заказа {order_id}</b>"
        )
        await callback.answer("📸 Скриншот отправлен в ЛС")
    except Exception as e:
        logger.error(f"Ошибка отправки скриншота: {e}")
        await callback.answer("❌ Ошибка отправки скриншота", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("confirm_order_"))
async def confirm_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("confirm_order_", "")
    
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    success = confirm_order(order_id, callback.from_user.id)
    
    if success:
        order = orders[order_id]
        user = users.get(order.user_id)
        card = cards.get(order.card_id)
        
        try:
            await callback.message.edit_text(
                f"✅ <b>Заказ подтвержден!</b>\n\n"
                f"🆔 Заказ: {order_id}\n"
                f"👤 Пользователь: @{user.username if user else 'неизвестно'}\n"
                f"🎴 Карточка: {card.name if card else 'неизвестно'}\n"
                f"💰 Сумма: {order.price}₽\n\n"
                f"Карточка добавлена в инвентарь пользователя."
            )
            await callback.answer("✅ Заказ подтвержден!")
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админу: {e}")
            await callback.message.answer(
                f"✅ <b>Заказ подтвержден!</b>\n\n"
                f"🆔 Заказ: {order_id}\n"
                f"👤 Пользователь: @{user.username if user else 'неизвестно'}\n"
                f"🎴 Карточка: {card.name if card else 'неизвестно'}\n"
                f"💰 Сумма: {order.price}₽\n\n"
                f"Карточка добавлена в инвентарь пользователя."
            )
            await callback.answer("✅ Заказ подтвержден!")
        
        if user and card:
            try:
                await send_order_notification(order_id, user.user_id, card.name, order.price)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю: {e}")
                logger.info(f"Пользователь {user.user_id} требует ручного уведомления о заказе {order_id}")
        else:
            logger.error(f"Данные пользователя или карточки для заказа {order_id} не найдены")
    else:
        await callback.answer("❌ Ошибка подтверждения заказа", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("reject_order_"))
async def reject_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("reject_order_", "")
    
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    success = reject_order(order_id, callback.from_user.id)
    
    if success:
        order = orders[order_id]
        user = users.get(order.user_id)
        card = cards.get(order.card_id)
        
        try:
            await callback.message.edit_text(
                f"❌ <b>Заказ отклонен!</b>\n\n"
                f"🆔 Заказ: {order_id}\n"
                f"👤 Пользователь: @{user.username if user else 'неизвестно'}\n"
                f"🎴 Карточка: {card.name if card else 'неизвестно'}\n"
                f"💰 Сумма: {order.price}₽\n\n"
                f"Карточка возвращена в магазин."
            )
            await callback.answer("❌ Заказ отклонен!")
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админу: {e}")
            await callback.message.answer(
                f"❌ <b>Заказ отклонен!</b>\n\n"
                f"🆔 Заказ: {order_id}\n"
                f"👤 Пользователь: @{user.username if user else 'неизвестно'}\n"
                f"🎴 Карточка: {card.name if card else 'неизвестно'}\n"
                f"💰 Сумма: {order.price}₽\n\n"
                f"Карточка возвращена в магазин."
            )
            await callback.answer("❌ Заказ отклонен!")
        
        if user:
            try:
                await bot.send_message(
                    user.user_id,
                    text=f"❌ <b>Ваш заказ отклонен!</b>\n\n"
                         f"🆔 Заказ: {order_id}\n"
                         f"🎴 Карточка: <b>{card.name if card else 'неизвестно'}</b>\n"
                         f"💰 Сумма: {order.price}₽\n\n"
                         f"Причина: оплата не подтверждена администратором.\n\n"
                         f"<i>Если вы считаете это ошибкой, свяжитесь с @prikolovwork</i>",
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Уведомление об отклонении отправлено пользователю {user.user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user.user_id}: {e}")
                logger.info(f"Пользователь {user.user_id} требует ручного уведомления об отклонении заказа {order_id}")
        else:
            logger.error(f"Пользователь для заказа {order_id} не найден")
            
    else:
        await callback.answer("❌ Ошибка отклонения заказа", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("notify_user_"))
async def notify_user_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("notify_user_", "")
    
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order = orders[order_id]
    user = users.get(order.user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await callback.message.answer(
        f"👤 <b>Отправить сообщение пользователю</b>\n\n"
        f"Пользователь: @{user.username}\n"
        f"Заказ: {order_id}\n\n"
        f"Введите сообщение для пользователя:"
    )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_orders_confirmed")
async def admin_orders_confirmed_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    confirmed_orders = [o for o in orders.values() if o.status == "confirmed"]
    
    if not confirmed_orders:
        await callback.message.answer("✅ <b>Подтвержденные заказы</b>\n\nНет подтвержденных заказов.")
        await callback.answer()
        return
    
    confirmed_orders.sort(key=lambda o: o.confirmed_at or o.created_at, reverse=True)
    
    response = f"✅ <b>Подтвержденные заказы ({len(confirmed_orders)})</b>\n\n"
    
    for i, order in enumerate(confirmed_orders[:10], 1):
        user = users.get(order.user_id)
        card = cards.get(order.card_id)
        
        if user and card:
            confirmed = datetime.fromisoformat(order.confirmed_at or order.created_at).strftime('%d.%m %H:%M')
            response += f"{i}. <b>{order.order_id}</b>\n"
            response += f"👤 @{user.username} | 🎴 {card.name} | 💰 {order.price}₽\n"
            response += f"✅ {confirmed}\n\n"
    
    response += f"<i>Показано последних 10 из {len(confirmed_orders)} заказов</i>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад к заказам", 
        callback_data="admin_orders"
    ))
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_orders_rejected")
async def admin_orders_rejected_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    rejected_orders = [o for o in orders.values() if o.status == "rejected"]
    
    if not rejected_orders:
        await callback.message.answer("❌ <b>Отклоненные заказы</b>\n\nНет отклоненных заказов.")
        await callback.answer()
        return
    
    rejected_orders.sort(key=lambda o: o.confirmed_at or o.created_at, reverse=True)
    
    response = f"❌ <b>Отклоненные заказы ({len(rejected_orders)})</b>\n\n"
    
    for i, order in enumerate(rejected_orders[:10], 1):
        user = users.get(order.user_id)
        card = cards.get(order.card_id)
        
        if user and card:
            rejected = datetime.fromisoformat(order.confirmed_at or order.created_at).strftime('%d.%m %H:%M')
            response += f"{i}. <b>{order.order_id}</b>\n"
            response += f"👤 @{user.username} | 🎴 {card.name} | 💰 {order.price}₽\n"
            response += f"❌ {rejected}\n\n"
    
    response += f"<i>Показано последних 10 из {len(rejected_orders)} заказов</i>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад к заказам", 
        callback_data="admin_orders"
    ))
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_orders_stats")
async def admin_orders_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    orders_by_day = {}
    total_revenue = 0
    
    for order in orders.values():
        if order.status == "confirmed":
            date = datetime.fromisoformat(order.confirmed_at or order.created_at).strftime('%d.%m.%Y')
            orders_by_day[date] = orders_by_day.get(date, 0) + 1
            total_revenue += order.price
    
    rarity_stats = {}
    for order in orders.values():
        if order.status == "confirmed":
            card = cards.get(order.card_id)
            if card:
                rarity_stats[card.rarity] = rarity_stats.get(card.rarity, 0) + 1
    
    response = (
        f"📊 <b>Статистика по заказам</b>\n\n"
        f"📈 <b>Общая статистика:</b>\n"
        f"Всего заказов: {len(orders)}\n"
        f"✅ Подтверждено: {len([o for o in orders.values() if o.status == 'confirmed'])}\n"
        f"❌ Отклонено: {len([o for o in orders.values() if o.status == 'rejected'])}\n"
        f"⏳ Ожидают: {len([o for o in orders.values() if o.status == 'pending'])}\n"
        f"💰 Общая выручка: {total_revenue}₽\n\n"
    )
    
    if orders_by_day:
        response += f"📅 <b>Заказов по дням (последние 7):</b>\n"
        sorted_days = sorted(orders_by_day.items(), key=lambda x: x[0], reverse=True)[:7]
        for date, count in sorted_days:
            response += f"{date}: {count} заказов\n"
        response += "\n"
    
    if rarity_stats:
        response += f"🎴 <b>Заказов по редкостям:</b>\n"
        for rarity in ["basic", "cool", "legendary", "vinyl figure"]:
            count = rarity_stats.get(rarity, 0)
            name = get_rarity_name(rarity)
            icon = get_rarity_color(rarity)
            if count > 0:
                response += f"{icon} {name}: {count}\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад к заказам", 
        callback_data="admin_orders"
    ))
    
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_level_system")
async def admin_level_system_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardBuilder()
    
    status = "✅ ВКЛЮЧЕНА" if LEVEL_SETTINGS['enabled'] else "❌ ВЫКЛЮЧЕНА"
    
    keyboard.add(InlineKeyboardButton(
        text=f"🔄 {status}", 
        callback_data="toggle_level_system"
    ))
    keyboard.add(InlineKeyboardButton(
        text="⚙️ Настройки опыта", 
        callback_data="level_exp_settings"
    ))
    keyboard.add(InlineKeyboardButton(
        text="📊 Статистика уровней", 
        callback_data="level_stats"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🎯 Сбросить прогресс игрока", 
        callback_data="reset_player_level"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data="admin_back"
    ))
    keyboard.adjust(1)
    
    total_players = len(users)
    avg_level = sum(u.level for u in users.values()) / total_players if total_players > 0 else 0
    max_level = max((u.level for u in users.values()), default=0)
    
    await callback.message.answer(
        f"⚙️ <b>Управление системой уровней</b>\n\n"
        f"📊 Статистика:\n"
        f"• Статус: {status}\n"
        f"• Всего игроков: {total_players}\n"
        f"• Средний уровень: {avg_level:.1f}\n"
        f"• Максимальный уровень: {max_level}\n"
        f"• Игроков 10+ уровня: {len([u for u in users.values() if u.level >= 10])}\n\n"
        f"<b>Текущие настройки опыта:</b>\n"
        f"• Открытие карточки: {LEVEL_SETTINGS['exp_actions']['open_card']} XP\n"
        f"• Покупка карточки: {LEVEL_SETTINGS['exp_actions']['purchase_card']} XP\n"
        f"• Обмен: {LEVEL_SETTINGS['exp_actions']['trade_complete']} XP\n"
        f"• Ежедневный вход: {LEVEL_SETTINGS['exp_actions']['daily_login']} XP\n\n"
        f"Выберите действие:",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "toggle_level_system")
async def toggle_level_system_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    LEVEL_SETTINGS['enabled'] = not LEVEL_SETTINGS['enabled']
    status = "✅ ВКЛЮЧЕНА" if LEVEL_SETTINGS['enabled'] else "❌ ВЫКЛЮЧЕНА"
    
    await callback.answer(f"Система уровней: {status}", show_alert=True)
    await admin_level_system_handler(callback)

@dp.callback_query(lambda c: c.data == "level_stats")
async def level_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    total_players = len(users)
    avg_level = sum(u.level for u in users.values()) / total_players if total_players > 0 else 0
    max_level = max((u.level for u in users.values()), default=0)
    total_exp = sum(u.total_exp_earned for u in users.values())
    
    level_distribution = {}
    for user in users.values():
        level_distribution[user.level] = level_distribution.get(user.level, 0) + 1
    
    response = "📊 <b>Статистика системы уровней</b>\n\n"
    response += f"• Всего игроков: {total_players}\n"
    response += f"• Средний уровень: {avg_level:.1f}\n"
    response += f"• Максимальный уровень: {max_level}\n"
    response += f"• Всего заработано опыта: {total_exp:,} XP\n\n"
    
    response += "<b>Распределение по уровням:</b>\n"
    for level in sorted(level_distribution.keys())[:20]:
        count = level_distribution[level]
        percentage = (count / total_players) * 100 if total_players > 0 else 0
        response += f"Уровень {level}: {count} игроков ({percentage:.1f}%)\n"
    
    await callback.message.answer(response)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await cmd_admin(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_ban_user")
async def admin_ban_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "⛔ <b>Бан пользователя</b>\n\n"
        "Введите username пользователя для бана (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_ban_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_ban_username)
async def process_ban_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    await state.update_data(ban_username=username, ban_user=user)
    
    await message.answer(
        f"⛔ <b>Бан пользователя @{username}</b>\n\n"
        "Введите причину бана:"
    )
    await state.set_state(AdminStates.waiting_for_ban_reason)
    await state.update_data(ban_username=username)

@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    reason = message.text
    data = await state.get_data()
    username = data.get('ban_username')
    
    if not username:
        await message.answer("❌ Ошибка: username не найден.")
        await state.clear()
        return
    
    user = get_user_by_username(username)
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    await state.update_data(ban_reason=reason, ban_user=user)
    
    await message.answer(
        f"⛔ <b>Бан пользователя @{username}</b>\n\n"
        f"Причина: {reason}\n\n"
        "Введите количество дней бана (0 для перманентного бана):"
    )
    await state.set_state(AdminStates.waiting_for_ban_days)

@dp.message(AdminStates.waiting_for_ban_days)
async def process_ban_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    try:
        days = int(message.text)
        if days < 0:
            await message.answer("❌ Количество дней должно быть положительным числом или 0.")
            await state.clear()
            return
    except ValueError:
        await message.answer("❌ Введите число (количество дней).")
        return
    
    data = await state.get_data()
    username = data.get('ban_username')
    reason = data.get('ban_reason')
    user = data.get('ban_user')
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return
    
    ban_user(user, reason, days)
    
    if days == 0:
        duration = "навсегда"
    else:
        duration = f"на {days} дней"
    
    await message.answer(
        f"✅ <b>Пользователь забанен!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"⛔ Длительность: {duration}\n"
        f"📝 Причина: {reason}"
    )
    
    try:
        if days == 0:
            duration_msg = "навсегда"
        else:
            duration_msg = f"на {days} дней"
        
        await bot.send_message(
            user.user_id,
            f"⛔ <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"Длительность: {duration_msg}\n"
            f"Причина: {reason}\n\n"
            f"Если вы считаете это ошибкой, свяжитесь с администратором."
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_unban_user")
async def admin_unban_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "✅ <b>Разбан пользователя</b>\n\n"
        "Введите username пользователя для разбана (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_unban_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_unban_username)
async def process_unban_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    if not user.is_banned:
        await message.answer(f"❌ Пользователь @{username} не забанен.")
        await state.clear()
        return
    
    user.is_banned = False
    user.ban_reason = None
    user.banned_until = None
    update_user_interaction(user)
    
    await message.answer(
        f"✅ <b>Пользователь разбанен!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "✅ <b>Ваш аккаунт разблокирован!</b>\n\n"
            "Теперь вы снова можете пользоваться ботом.\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_freeze_user")
async def admin_freeze_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "❄️ <b>Заморозка аккаунта</b>\n\n"
        "Введите username пользователя для заморозки (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_freeze_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_freeze_username)
async def process_freeze_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    await state.update_data(freeze_username=username, freeze_user=user)
    
    await message.answer(
        f"❄️ <b>Заморозка аккаунта @{username}</b>\n\n"
        "Введите количество дней заморозки (0 для перманентной заморозки):"
    )
    await state.set_state(AdminStates.waiting_for_freeze_days)

@dp.message(AdminStates.waiting_for_freeze_days)
async def process_freeze_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    try:
        days = int(message.text)
        if days < 0:
            await message.answer("❌ Количество дней должно быть положительным числом или 0.")
            await state.clear()
            return
    except ValueError:
        await message.answer("❌ Введите число (количество дней).")
        return
    
    data = await state.get_data()
    username = data.get('freeze_username')
    user = data.get('freeze_user')
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return
    
    user.is_frozen = True
    
    if days > 0:
        frozen_until = datetime.now() + timedelta(days=days)
        user.frozen_until = frozen_until.isoformat()
        duration = f"до {frozen_until.strftime('%d.%m.%Y %H:%M')}"
    else:
        user.frozen_until = None
        duration = "навсегда"
    
    update_user_interaction(user)
    
    await message.answer(
        f"✅ <b>Аккаунт заморожен!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"❄️ Длительность: {duration}"
    )
    
    try:
        if days == 0:
            duration_msg = "навсегда"
        else:
            duration_msg = f"до {frozen_until.strftime('%d.%m.%Y %H:%M')}"
        
        await bot.send_message(
            user.user_id,
            f"❄️ <b>Ваш аккаунт заморожен!</b>\n\n"
            f"Длительность: {duration_msg}\n\n"
            f"Если вы считаете это ошибкой, свяжитесь с администратором."
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_unfreeze_user")
async def admin_unfreeze_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "☀️ <b>Разморозка аккаунта</b>\n\n"
        "Введите username пользователя для разморозки (начиная с @):"
    )
    await state.set_state(AdminStates.waiting_for_unfreeze_username)
    await callback.answer()

@dp.message(AdminStates.waiting_for_unfreeze_username)
async def process_unfreeze_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        await state.clear()
        return
    
    if not user.is_frozen:
        await message.answer(f"❌ Аккаунт @{username} не заморожен.")
        await state.clear()
        return
    
    user.is_frozen = False
    user.frozen_until = None
    update_user_interaction(user)
    
    await message.answer(
        f"✅ <b>Аккаунт разморожен!</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        await bot.send_message(
            user.user_id,
            "☀️ <b>Ваш аккаунт разморожен!</b>\n\n"
            "Теперь вы снова можете пользоваться ботом.\n\n"
            "Приятной игры! 🎴"
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_database")
async def admin_database_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer_document(
        document=FSInputFile(USERS_FILE),
        caption="📥 <b>База данных пользователей</b>\n\n"
               f"Всего пользователей: {len(users)}"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_update_pool")
async def admin_update_pool_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    update_card_pool()
    await callback.answer("✅ Пул карточек обновлен!")
    
    rarity_counts = {}
    for card in cards.values():
        rarity_counts[card.rarity] = rarity_counts.get(card.rarity, 0) + 1
    
    stats = "Распределение по редкостям:\n"
    for rarity in ["basic", "cool", "legendary", "vinyl figure"]:
        count = rarity_counts.get(rarity, 0)
        name = get_rarity_name(rarity)
        icon = get_rarity_color(rarity)
        stats += f"{icon} {name}: {count} карточек\n"
    
    await callback.message.answer(
        f"🔄 <b>Пул карточек обновлен</b>\n\n"
        f"Всего карточек: {len(cards)}\n"
        f"Записей в пуле: {len(card_pool)}\n\n"
        f"{stats}"
    )

@dp.callback_query(lambda c: c.data == "admin_restart")
async def admin_restart_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "🔄 <b>Перезапуск бота</b>\n\n"
        "Бот будет перезапущен...\n"
        "Это может занять несколько секунд."
    )
    
    save_data()
    await callback.answer("✅ Данные сохранены, бот готов к перезапуску!")

@dp.message(Command("addexclusive"))
async def add_exclusive_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer(
                "❌ <b>Формат команды:</b>\n"
                "<code>/addexclusive card_id total_copies price [days]</code>\n\n"
                "Пример:\n"
                "<code>/addexclusive card_123 100 499 30</code> - 100 копий по 499₽ на 30 дней\n"
                "<code>/addexclusive card_456 50 999</code> - 50 копий по 999₽ бессрочно"
            )
            return
        
        card_id = parts[1]
        total_copies = int(parts[2])
        price = int(parts[3])
        
        if card_id not in cards:
            await message.answer(f"❌ Карточка {card_id} не найдена в системе")
            return
        
        if len(parts) >= 5:
            days = int(parts[4])
            end_date = datetime.now() + timedelta(days=days)
            end_date_str = end_date.isoformat()
        else:
            end_date_str = None
        
        exclusive = ExclusiveCard(
            card_id=card_id,
            total_copies=total_copies,
            price=price,
            end_date=end_date_str
        )
        
        exclusive_cards[card_id] = exclusive
        save_data()
        
        card = cards[card_id]
        response = f"✅ <b>Эксклюзивная карточка добавлена!</b>\n\n"
        response += f"🎴 <b>Карточка:</b> {card.name}\n"
        response += f"📦 <b>Копий:</b> {total_copies}\n"
        response += f"💰 <b>Цена:</b> {price}₽\n"
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
            response += f"📅 <b>Доступна до:</b> {end_date.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            response += f"📅 <b>Доступна:</b> бессрочно\n"
        
        response += f"\nТеперь карточка доступна в разделе 🎪 Эксклюзивы"
        
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def periodic_tasks():
    while True:
        try:
            for user in users.values():
                if random.random() < 0.01:
                    await send_personal_offer(user.user_id)
            
            now = datetime.now()
            for exclusive in exclusive_cards.values():
                if exclusive.end_date and datetime.fromisoformat(exclusive.end_date) < now:
                    exclusive.is_active = False
            
            save_data()
            
        except Exception as e:
            logger.error(f"Ошибка в периодических задачах: {e}")
        
        await asyncio.sleep(300)

async def send_personal_offer(user_id: int):
    user = users.get(user_id)
    if not user or user.is_banned or user.is_frozen:
        return
    
    user_orders = [o for o in orders.values() 
                   if o.user_id == user_id 
                   and o.status == "confirmed"]
    
    if not user_orders:
        try:
            await bot.send_message(
                user_id,
                "🎁 <b>Специальное предложение для новичка!</b>\n\n"
                "При первой покупке получите:\n"
                "• +20% к опыту\n"
                "• 1 случайную карточку в подарок\n"
                "• Статус 'Начинающий коллекционер'\n\n"
                "Ждем вас в магазине! 🛒"
            )
        except:
            pass
    else:
        last_order = max(user_orders, key=lambda o: datetime.fromisoformat(o.confirmed_at or o.created_at))
        days_since = (datetime.now() - datetime.fromisoformat(last_order.confirmed_at or last_order.created_at)).days
        
        if days_since >= 7:
            try:
                discount = min(25, 10 + (days_since // 7) * 5)
                
                await bot.send_message(
                    user_id,
                    f"🎯 <b>Скучаем по вам! Персональная скидка {discount}%</b>\n\n"
                    f"Мы заметили, что вы давно не заглядывали в магазин.\n"
                    f"Специально для вас - скидка {discount}% на любую покупку!\n\n"
                    f"⏰ Действует 24 часа\n"
                    f"🎁 Код: LOYAL{discount}\n\n"
                    f"Ждем вас! 🛒"
                )
            except:
                pass

async def main():
    load_data()
    
    logger.info("=" * 50)
    logger.info("Бот Фанко запускается...")
    logger.info(f"Python {sys.version}")
    logger.info(f"Пользователей в базе: {len(users)}")
    logger.info(f"Карточек в системе: {len(cards)}")
    logger.info(f"Заказов в системе: {len(orders)}")
    logger.info(f"Канал для подписки: {CHANNEL_USERNAME}")
    logger.info(f"Защита от спама: {MESSAGE_LIMIT} сообщений/{TIME_WINDOW} сек")
    logger.info(f"Напоминания о неактивности: каждые {INACTIVITY_DAYS} дней")
    logger.info("=" * 50)
    
    try:
        asyncio.create_task(check_inactive_users())
        
        asyncio.create_task(periodic_tasks())
        
        logger.info("🔄 Запуск поллинга...")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        logger.info("Попробуйте:")
        logger.info("1. Проверить интернет-соединение")
        logger.info("2. Убедиться что токен бота правильный")
        logger.info("3. Проверить настройки сети/прокси")
        
        save_data()
        logger.info("✅ Данные сохранены")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
        save_data()
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")
        save_data()

