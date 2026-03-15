# models.py — Классы данных
from typing import Dict, Optional, List
from datetime import datetime
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
current_wheel: Optional['FortuneWheel'] = None
promo_manager: Optional['PromoCodeManager'] = None

def get_level_discount(level: int) -> int:
    discount_per_15_levels = 2
    discount = (level // 15) * discount_per_15_levels
    return min(discount, 20)

def get_price_with_discount(original_price: int, level: int) -> int:
    discount = get_level_discount(level)
    if discount > 0:
        discounted = original_price * (100 - discount) // 100
        return max(discounted, 1)
    return original_price

def get_token_price(ruble_price: int) -> int:
    token_price = ruble_price * 1.5
    return int(token_price) + (1 if token_price % 1 > 0 else 0)

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
        self.daily_bonus_claimed: Optional[str] = None      # premium daily (legacy)
        self.daily_wheel_claimed: Optional[str] = None      # бесплатный ежедневный спин для всех
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

        # ─── Секретный магазин ───
        self.last_secret_shop_notified: Optional[str] = None   # когда последний раз получил уведомление
        self.secret_shop_expires: Optional[str] = None         # до когда активен доступ

        # ─── Реферальный конкурс ───
        self.referral_contest_season: int = 0     # номер сезона, в котором уже получили награду
        self.referral_contest_month_refs: int = 0 # рефералы этого месяца (сбрасываются)

        # ─── Еженедельные ивенты ───
        # event_contributions: {"event_id": score}
        self.event_contributions: Dict[str, int] = {}

        # ─── Косметика ───
        self.active_title: str = "Новичок"
        self.unlocked_titles: List[str] = ["Новичок"]

        # ─── Динамические цены (покупки по флэш-ценам) ───
        self.orders_confirmed_count: int = 0  # для титула Меценат


class Card:
    def __init__(self, card_id: str, name: str, rarity: str, image_filename: str = ""):
        self.card_id = card_id
        self.name = name
        self.rarity = rarity
        self.image_filename = image_filename


class ShopItem:
    def __init__(self, card_id: str, price: int, expires_at: str,
                 original_price: int = 0, flash_sale_until: Optional[str] = None):
        self.card_id = card_id
        self.price = price
        self.original_price = original_price or price   # цена до флэш-скидки
        self.expires_at = expires_at
        self.flash_sale_until: Optional[str] = flash_sale_until  # до когда действует флэш-скидка


class Order:
    def __init__(self, order_id: str, user_id: int, card_id: str, price: int,
                 status: str = "pending", gift_to_user_id: Optional[int] = None):
        self.order_id = order_id
        self.user_id = user_id           # кто платит
        self.card_id = card_id
        self.price = price
        self.status = status
        self.created_at = datetime.now().isoformat()
        self.confirmed_at: Optional[str] = None
        self.admin_id: Optional[int] = None
        self.payment_proof: Optional[str] = None
        self.gift_to_user_id: Optional[int] = gift_to_user_id   # кому подарок (None = себе)


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


class WeeklyEvent:
    """Еженедельный ивент."""
    def __init__(self, event_id: str, event_type: str, start_time: str, end_time: str):
        self.event_id = event_id
        self.event_type = event_type      # "open_cards" | "collect_legendaries" | "win_games" | "collect_tokens"
        self.start_time = start_time
        self.end_time = end_time
        self.scores: Dict[int, int] = {}  # user_id → score
        self.prizes_distributed = False

    def add_score(self, user_id: int, amount: int = 1):
        self.scores[user_id] = self.scores.get(user_id, 0) + amount

    def get_top(self, limit: int = 10) -> List[tuple]:
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:limit]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
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
    """Ежемесячный реферальный конкурс."""
    def __init__(self, season: int, start_time: str, end_time: str):
        self.season = season
        self.start_time = start_time
        self.end_time = end_time
        self.prizes_distributed = False

    def to_dict(self) -> dict:
        return {
            "season": self.season,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "prizes_distributed": self.prizes_distributed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReferralContest':
        rc = cls(data["season"], data["start_time"], data["end_time"])
        rc.prizes_distributed = data.get("prizes_distributed", False)
        return rc
