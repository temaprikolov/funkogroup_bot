# models.py — Классы данных
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from games import GameStats


class NotificationSettings:
    def __init__(self):
        self.shop_updates = True
        self.card_available = True
        self.promo_offers = True
        self.trade_offers = True
        self.system_messages = True


# Глобальные хранилища (заполняются из main.py)
users: Dict[int, 'User'] = {}
cards: Dict[str, 'Card'] = {}
card_pool: List[str] = []
premium_card_pool: List[str] = []
trades: Dict[str, Dict] = {}
user_inventory_pages: Dict[int, Dict] = {}
shop_items: Dict[str, 'ShopItem'] = {}
orders: Dict[str, 'Order'] = {}
exclusive_cards: Dict[str, 'ExclusiveCard'] = {}
card_popularity: Dict[str, Dict] = {}
active_game_challenges: Dict[str, 'GameChallenge'] = {}
market_listings: Dict[str, 'MarketListing'] = {}
current_wheel: Optional['FortuneWheel'] = None
promo_manager: Optional['PromoCodeManager'] = None
lootboxes: Dict[str, 'Lootbox'] = {}


def get_level_discount(level: int) -> int:
    return min((level // 15) * 2, 20)

def get_price_with_discount(original_price: int, level: int) -> int:
    discount = get_level_discount(level)
    if discount > 0:
        return max(original_price * (100 - discount) // 100, 1)
    return original_price

def get_token_price(ruble_price: int) -> int:
    tp = ruble_price * 1.5
    return int(tp) + (1 if tp % 1 > 0 else 0)

def is_video_card(card: 'Card') -> bool:
    return bool(card.image_filename and card.image_filename.endswith('.mp4'))


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
        self.daily_wheel_claimed: Optional[str] = None
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
        self.referrals: List[int] = []
        self.referrer_id: Optional[int] = None
        self.referral_bonus_claimed = False
        self.notification_settings = NotificationSettings()
        self.skip_card_cooldown_available = False
        self.skip_trade_cooldown_available = False
        self.tokens = 0
        self.game_stats = GameStats()
        self.last_lucky_dice_time: Optional[str] = None

        # Секретный магазин
        self.last_secret_shop_notified: Optional[str] = None
        self.secret_shop_expires: Optional[str] = None

        # Реферальный конкурс
        self.referral_contest_season: int = 0
        self.referral_contest_month_refs: int = 0

        # Еженедельные ивенты
        self.event_contributions: Dict[str, int] = {}

        # Косметика
        self.active_title: str = "Новичок"
        self.unlocked_titles: List[str] = ["Новичок"]
        self.orders_confirmed_count: int = 0

        # Ежедневный стрик
        self.daily_streak: int = 0
        self.last_streak_date: Optional[str] = None

        # Вишлист
        self.wishlist: List[str] = []

        # Система достижений
        self.achievements: Dict[str, str] = {}

        # Умные напоминания
        self.cooldown_notified: bool = False

        # Статистика для достижений
        self.total_trades: int = 0
        self.total_gifts: int = 0
        self.total_crafts: int = 0
        self.total_crafted_legendary: int = 0
        self.market_sold_count: int = 0
        self.market_bought_count: int = 0


class Card:
    def __init__(self, card_id: str, name: str, rarity: str,
                 image_filename: str = "", image_file_id: str = ""):
        self.card_id = card_id
        self.name = name
        self.rarity = rarity
        self.image_filename = image_filename
        self.image_file_id: str = image_file_id


class ShopItem:
    def __init__(self, card_id: str, price: int, expires_at: str,
                 original_price: int = 0, flash_sale_until: Optional[str] = None):
        self.card_id = card_id
        self.price = price
        self.original_price = original_price or price
        self.expires_at = expires_at
        self.flash_sale_until: Optional[str] = flash_sale_until


class Order:
    def __init__(self, order_id: str, user_id: int, card_id: str, price: int,
                 status: str = "pending", gift_to_user_id: Optional[int] = None):
        self.order_id = order_id
        self.user_id = user_id
        self.card_id = card_id
        self.price = price
        self.status = status
        self.created_at = datetime.now().isoformat()
        self.confirmed_at: Optional[str] = None
        self.admin_id: Optional[int] = None
        self.payment_proof: Optional[str] = None
        self.gift_to_user_id: Optional[int] = gift_to_user_id


class ExclusiveCard:
    def __init__(self, card_id: str, total_copies: int, price: int,
                 end_date: Optional[str] = None):
        self.card_id = card_id
        self.total_copies = total_copies
        self.sold_copies = 0
        self.price = price
        self.original_price = price
        self.end_date = end_date
        self.is_active = True
        self.flash_sale_until: Optional[str] = None

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


# Токен-рынок
MARKET_LISTING_DAYS = 3
MARKET_FEE_PCT = 10
MARKET_MIN_PRICE = 1
MARKET_MAX_PRICE = 10_000


class MarketListing:
    def __init__(self, listing_id: str, seller_id: int, card_id: str, price_tokens: int):
        self.listing_id = listing_id
        self.seller_id = seller_id
        self.card_id = card_id
        self.price_tokens = price_tokens
        self.created_at = datetime.now().isoformat()
        self.expires_at = (datetime.now() + timedelta(days=MARKET_LISTING_DAYS)).isoformat()
        self.is_active = True

    def is_expired(self) -> bool:
        return datetime.fromisoformat(self.expires_at) <= datetime.now()

    def to_dict(self) -> dict:
        return {
            'listing_id': self.listing_id,
            'seller_id': self.seller_id,
            'card_id': self.card_id,
            'price_tokens': self.price_tokens,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'is_active': self.is_active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'MarketListing':
        ml = cls(d['listing_id'], d['seller_id'], d['card_id'], d['price_tokens'])
        ml.created_at = d['created_at']
        ml.expires_at = d['expires_at']
        ml.is_active = d['is_active']
        return ml


# Ивенты
class WeeklyEvent:
    def __init__(self, event_id: str, event_type: str, start_time: str, end_time: str):
        self.event_id = event_id
        self.event_type = event_type
        self.start_time = start_time
        self.end_time = end_time
        self.scores: Dict[int, int] = {}
        self.prizes_distributed = False

    def add_score(self, user_id: int, amount: int = 1):
        self.scores[user_id] = self.scores.get(user_id, 0) + amount

    def get_top(self, limit: int = 10) -> List[tuple]:
        return sorted(self.scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "event_type": self.event_type,
            "start_time": self.start_time, "end_time": self.end_time,
            "scores": {str(k): v for k, v in self.scores.items()},
            "prizes_distributed": self.prizes_distributed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WeeklyEvent':
        ev = cls(data["event_id"], data["event_type"], data["start_time"], data["end_time"])
        ev.scores = {int(k): v for k, v in data.get("scores", {}).items()}
        ev.prizes_distributed = data.get("prizes_distributed", False)
        return ev


class ReferralContest:
    def __init__(self, season: int, start_time: str, end_time: str):
        self.season = season
        self.start_time = start_time
        self.end_time = end_time
        self.prizes_distributed = False

    def to_dict(self) -> dict:
        return {
            "season": self.season, "start_time": self.start_time,
            "end_time": self.end_time, "prizes_distributed": self.prizes_distributed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReferralContest':
        rc = cls(data["season"], data["start_time"], data["end_time"])
        rc.prizes_distributed = data.get("prizes_distributed", False)
        return rc


# ════════════════════════════════════════════════════════════════════════════════
# НОВЫЕ МОДЕЛИ ДЛЯ РАСШИРЕННОЙ АДМИНКИ
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class Lootbox:
    """Лутбокс"""
    lootbox_id: str
    name: str
    price: int
    description: str = ""
    contents: List[Dict] = field(default_factory=list)
    image_file_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    active: bool = True
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class WheelPrize:
    """Приз для колеса фортуны"""
    prize_id: str
    name: str
    prize_type: str  # "tokens", "card", "premium", "nothing"
    value: int = 0
    card_id: Optional[str] = None
    chance: float = 10.0
    color: str = "#FFD700"
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class FortuneWheelConfig:
    """Конфигурация колеса фортуны для расширенной админки.
    BUG FIX: renamed from FortuneWheel to avoid conflict with games.FortuneWheel
    which is the actual runtime wheel class used in main.py.
    """
    wheel_id: str
    name: str
    prizes: List[WheelPrize] = field(default_factory=list)
    spin_cost: int = 50
    free_spins_per_day: int = 1
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        data = asdict(self)
        data['prizes'] = [p.to_dict() for p in self.prizes]
        return data
    
    @classmethod
    def from_dict(cls, data):
        prizes_data = data.pop('prizes', [])
        wheel = cls(**data)
        wheel.prizes = [WheelPrize.from_dict(p) for p in prizes_data]
        return wheel


@dataclass
class Quest:
    """Квест"""
    quest_id: str
    name: str
    description: str
    goal_type: str  # "drops", "trades", "purchases", "collect_cards"
    goal_target: int
    reward_tokens: int = 0
    reward_card_id: Optional[str] = None
    reward_premium_days: int = 0
    duration_days: int = 7
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class UserQuest:
    """Прогресс пользователя по квесту"""
    quest_id: str
    progress: int = 0
    completed: bool = False
    claimed: bool = False
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Achievement:
    """Достижение"""
    achievement_id: str
    name: str
    description: str
    condition_type: str
    condition_value: int
    reward_tokens: int = 0
    reward_badge: str = ""
    hidden: bool = False
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class ABTest:
    """A/B тест"""
    test_id: str
    name: str
    item_type: str
    item_id: str
    group_a_price: int
    group_b_price: int
    group_a_conversions: int = 0
    group_b_conversions: int = 0
    group_a_revenue: int = 0
    group_b_revenue: int = 0
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Poll:
    """Опрос"""
    poll_id: str
    question: str
    options: List[str]
    votes: Dict[str, int] = field(default_factory=dict)
    multiple_choice: bool = False
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ends_at: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class MiniGame:
    """Мини-игра"""
    game_id: str
    name: str
    game_type: str  # "roulette", "rps", "guess_number", "dice"
    min_bet: int = 10
    max_bet: int = 1000
    win_chance: float = 45.0
    multiplier: float = 2.0
    enabled: bool = True
    jackpot: int = 0
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


# NOTE: GameChallenge and PromoCodeManager are real classes defined in games.py and promo.py.
# They were previously stubbed here which caused shadowing issues.
# Import them from their real modules when needed.
