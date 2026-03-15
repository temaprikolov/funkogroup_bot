# config.py
BOT_TOKEN = "8783170508:AAGw3mxHzVruHW14-OwWpEilIpMdaUQLomU"
ADMIN_IDS = [8033943956, 7571242177]

PREMIUM_COST = 143
REDUCED_CD_COST = 127
REDUCED_TRADE_CD_COST = 67

SKIP_CARD_COOLDOWN_COST = 39
SKIP_TRADE_COOLDOWN_COST = 19
BUY_LEVEL_1_COST = 39
BUY_LEVEL_5_COST = 149

SHOP_PRICES = {
    "basic": 53,
    "cool": 93,
    "legendary": 143,
    "vinyl figure": 193
}

# Цены в Telegram Stars
PREMIUM_STARS = 25
REDUCED_CD_STARS = 20
REDUCED_TRADE_CD_STARS = 10
SKIP_CARD_COOLDOWN_STARS = 7
SKIP_TRADE_COOLDOWN_STARS = 3
BUY_LEVEL_1_STARS = 7
BUY_LEVEL_5_STARS = 25
SHOP_PRICES_STARS = {
    "basic": 10,
    "cool": 15,
    "legendary": 25,
    "vinyl figure": 35
}

CHANNEL_ID = -1003750249832
CHANNEL_LINK = "https://t.me/funkopopcards"
CHANNEL_USERNAME = "@funkopopcards"

INACTIVITY_DAYS = 7
INACTIVITY_CHECK_INTERVAL = 3600

MESSAGE_LIMIT = 5
TIME_WINDOW = 1

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

# ─── Лутбоксы ───
LOOTBOX_PRICES = {
    "basic_pack":     {"rubles": 79,  "stars": 13, "tokens": 0,  "name": "📦 Базовый пак",     "cards": 3, "guaranteed": "basic"},
    "cool_pack":      {"rubles": 149, "stars": 25, "tokens": 0,  "name": "💠 Крутой пак",       "cards": 5, "guaranteed": "cool"},
    "legendary_pack": {"rubles": 249, "stars": 42, "tokens": 0,  "name": "✨ Легендарный пак",  "cards": 3, "guaranteed": "legendary"},
    "token_pack":     {"rubles": 0,   "stars": 0,  "tokens": 50, "name": "🎫 Токен-пак (50🎫)", "cards": 3, "guaranteed": "basic"},
}

# ─── Крафт карточек ───
CRAFT_RECIPES = {
    "basic_to_cool":      {"from": "basic",     "count": 3, "to": "cool",      "token_cost": 0,  "success_rate": 100},
    "cool_to_legendary":  {"from": "cool",      "count": 3, "to": "legendary", "token_cost": 0,  "success_rate": 50},
    "cool_to_leg_sure":   {"from": "cool",      "count": 5, "to": "legendary", "token_cost": 50, "success_rate": 100},
    "leg_to_vinyl":       {"from": "legendary", "count": 3, "to": "vinyl figure","token_cost":150,"success_rate": 30},
}

# ─── Секретный магазин ───
SECRET_SHOP_DISCOUNT_MIN = 30   # % скидки минимум
SECRET_SHOP_DISCOUNT_MAX = 40   # % скидки максимум
SECRET_SHOP_DURATION_MINUTES = 60
SECRET_SHOP_COOLDOWN_DAYS = 3   # Раз в N дней может придти одному юзеру
SECRET_SHOP_CHECK_INTERVAL = 3600  # Каждый час проверяем

# ─── Динамические цены ───
DYNAMIC_PRICE_DISCOUNT_MAX = 25  # Максимальный сброс в рублях
DYNAMIC_PRICE_MIN_MINUTES = 10
DYNAMIC_PRICE_MAX_MINUTES = 120
DYNAMIC_PRICE_CHECK_INTERVAL = 1800  # Проверка каждые 30 минут

# ─── Еженедельные ивенты ───
WEEKLY_EVENT_TYPES = ["open_cards", "collect_legendaries", "win_games", "collect_tokens"]
WEEKLY_EVENT_PRIZES = {
    1: {"tokens": 100, "premium_days": 7,  "extra": "skip_both"},
    2: {"tokens": 75,  "premium_days": 3,  "extra": "skip_both"},
    3: {"tokens": 50,  "premium_days": 0,  "extra": "skip_both"},
    4: {"tokens": 25,  "premium_days": 0,  "extra": ""},
    5: {"tokens": 25,  "premium_days": 0,  "extra": ""},
}

# ─── Реферальный конкурс ───
REFERRAL_CONTEST_PRIZES = {
    1:      {"tokens": 100, "vinyl_cards": 1, "premium_days": 30, "skips": 0,  "legendary_cards": 0, "cool_cards": 0},
    2:      {"tokens": 75,  "vinyl_cards": 0, "premium_days": 3,  "skips": 1,  "legendary_cards": 2, "cool_cards": 0},
    3:      {"tokens": 50,  "vinyl_cards": 0, "premium_days": 0,  "skips": 1,  "legendary_cards": 1, "cool_cards": 0},
    "4-10": {"tokens": 25,  "vinyl_cards": 0, "premium_days": 0,  "skips": 1,  "legendary_cards": 0, "cool_cards": 0},
}

# ─── Косметика / Титулы ───
TITLES = {
    "Новичок":          {"condition": "level", "value": 1,  "icon": "🌱"},
    "Коллекционер":     {"condition": "level", "value": 20, "icon": "📚"},
    "Легенда":          {"condition": "level", "value": 50, "icon": "⚡"},
    "Игрок":            {"condition": "wins",  "value": 50, "icon": "🎮"},
    "Чемпион":          {"condition": "wins",  "value": 200,"icon": "🏆"},
    "Щедрый":           {"condition": "referrals", "value": 10, "icon": "🤝"},
    "Меценат":          {"condition": "orders_confirmed", "value": 5, "icon": "💎"},
    "Коллекционер карт":{"condition": "unique_cards", "value": 20, "icon": "🃏"},
}
