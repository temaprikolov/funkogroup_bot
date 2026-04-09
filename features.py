# features.py — Стрики, достижения, карта дня, напоминания о кулдауне
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# 1. ЕЖЕДНЕВНЫЙ СТРИК
# ════════════════════════════════════════════════════════════════════════════════
# Токенов за N-й день подряд (7+ дней = максимум)
STREAK_REWARDS: Dict[int, int] = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 10}
STREAK_MAX_BONUS = 10


def update_daily_streak(user) -> Optional[int]:
    """
    Вызывать при каждом открытии карточки (open_fanco).
    Возвращает число начисленных бонусных токенов, или None если уже засчитано сегодня.
    """
    today     = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

    if getattr(user, 'last_streak_date', None) == today:
        return None  # уже засчитано

    prev = getattr(user, 'last_streak_date', None)
    if prev == yesterday:
        user.daily_streak = getattr(user, 'daily_streak', 0) + 1
    else:
        user.daily_streak = 1  # сброс (пропущен день)

    user.last_streak_date = today
    day_idx = min(user.daily_streak, 7)
    bonus = STREAK_REWARDS.get(day_idx, STREAK_MAX_BONUS)
    user.tokens = getattr(user, 'tokens', 0) + bonus
    return bonus


def streak_emoji(streak: int) -> str:
    if streak >= 30: return "🌟"
    if streak >= 14: return "🔥🔥"
    if streak >= 7:  return "🔥"
    if streak >= 3:  return "✨"
    return "⚡"


def _days_word(n: int) -> str:
    """Russian declension for 'день/дня/дней'."""
    if 11 <= (n % 100) <= 19:
        return "дней"
    r = n % 10
    if r == 1: return "день"
    if 2 <= r <= 4: return "дня"
    return "дней"


def streak_message(streak: int, bonus: int) -> str:
    emoji = streak_emoji(streak)
    next_bonus = STREAK_REWARDS.get(min(streak + 1, 7), STREAK_MAX_BONUS)
    lines = [
        f"{emoji} <b>Стрик: {streak} {_days_word(streak)} подряд!</b>",
        f"🎫 Бонус: +{bonus} токен{'ов' if bonus != 1 else ''}",
    ]
    if streak < 7:
        lines.append(f"➡️ Завтра: +{next_bonus}🎫")
    else:
        lines.append("🔥 Максимальный бонус достигнут!")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════════
# 2. КАРТА ДНЯ
# ════════════════════════════════════════════════════════════════════════════════
_featured_card_id: str   = ""
_featured_card_date: str = ""
FEATURED_SHOP_DISCOUNT  = 20   # % скидки в магазине
FEATURED_TOKEN_MULTIPLIER = 2  # множитель токенов при открытии


def get_featured_card(cards: dict) -> Optional[str]:
    """Возвращает card_id карты дня. Меняется раз в сутки."""
    global _featured_card_id, _featured_card_date
    today = datetime.now().date().isoformat()
    if _featured_card_date != today or _featured_card_id not in cards:
        if cards:
            _featured_card_id  = random.choice(list(cards.keys()))
            _featured_card_date = today
            logger.info(f"🃏 Карта дня: {_featured_card_id}")
    return _featured_card_id if _featured_card_id in cards else None


def is_featured_card(card_id: str, cards: dict) -> bool:
    return get_featured_card(cards) == card_id


def featured_shop_price(original_price: int) -> int:
    """Цена карты дня в магазине: −{FEATURED_SHOP_DISCOUNT}%."""
    return max(int(original_price * (100 - FEATURED_SHOP_DISCOUNT) / 100), 1)


def featured_card_info(cards: dict, get_rarity_color_fn, get_rarity_name_fn) -> str:
    """Текстовое описание карты дня для меню."""
    cid = get_featured_card(cards)
    if not cid:
        return ""
    card = cards.get(cid)
    if not card:
        return ""
    icon = get_rarity_color_fn(card.rarity)
    return (
        f"\n\n🃏 <b>Карта дня:</b> {icon} {card.name} "
        f"({get_rarity_name_fn(card.rarity)})\n"
        f"• В магазине: −{FEATURED_SHOP_DISCOUNT}%\n"
        f"• При открытии: х{FEATURED_TOKEN_MULTIPLIER} токенов"
    )


# ════════════════════════════════════════════════════════════════════════════════
# 3. СИСТЕМА ДОСТИЖЕНИЙ
# ════════════════════════════════════════════════════════════════════════════════
ACHIEVEMENTS: Dict[str, Dict] = {
    # ── Карточки ──────────────────────────────────────────────────────────────
    "first_card":          {"name": "Первый шаг",        "icon": "🌱", "desc": "Открыть первую карточку"},
    "first_legendary":     {"name": "Легенда",           "icon": "🟡", "desc": "Получить первую легендарную карточку"},
    "first_vinyl":         {"name": "Коллекционер",      "icon": "🟣", "desc": "Получить первую виниловую фигурку"},
    "cards_10":            {"name": "Новичок-коллектор", "icon": "📦", "desc": "10 карточек в коллекции"},
    "cards_50":            {"name": "Коллектор",         "icon": "📚", "desc": "50 карточек"},
    "cards_100":           {"name": "Мастер коллекции",  "icon": "🎖", "desc": "Открыть 100 карточек (всего)"},
    "unique_20":           {"name": "Разнообразие",      "icon": "🃏", "desc": "20 уникальных карточек"},
    "unique_50":           {"name": "Энциклопедия",      "icon": "📖", "desc": "50 уникальных карточек"},
    # ── Стрики ────────────────────────────────────────────────────────────────
    "streak_3":            {"name": "В ритме",           "icon": "✨", "desc": "3 дня подряд"},
    "streak_7":            {"name": "Неделя огня",       "icon": "🔥", "desc": "7 дней подряд"},
    "streak_30":           {"name": "Месяц огня",        "icon": "🌟", "desc": "30 дней подряд"},
    # ── Игры ──────────────────────────────────────────────────────────────────
    "first_win":           {"name": "Первая победа",     "icon": "🏅", "desc": "Выиграть игру"},
    "wins_10":             {"name": "Игрок",             "icon": "🎮", "desc": "10 побед"},
    "wins_50":             {"name": "Чемпион",           "icon": "🏆", "desc": "50 побед"},
    "wins_100":            {"name": "Легенда арены",     "icon": "👑", "desc": "100 побед"},
    # ── Уровни ────────────────────────────────────────────────────────────────
    "level_5":             {"name": "Опытный",           "icon": "⭐", "desc": "Уровень 5"},
    "level_10":            {"name": "Ветеран",           "icon": "💫", "desc": "Уровень 10"},
    "level_25":            {"name": "Мастер",            "icon": "💎", "desc": "Уровень 25"},
    "level_50":            {"name": "Полубог",           "icon": "🌈", "desc": "Уровень 50"},
    # ── Социальные ────────────────────────────────────────────────────────────
    "first_trade":         {"name": "Торговец",          "icon": "🤝", "desc": "Совершить первый обмен"},
    "trades_10":           {"name": "Опытный торговец",  "icon": "🏦", "desc": "10 обменов"},
    "first_gift":          {"name": "Щедрый",            "icon": "🎁", "desc": "Подарить карточку"},
    "gifts_5":             {"name": "Благотворитель",    "icon": "💝", "desc": "5 подарков"},
    "referral_1":          {"name": "Зазывала",          "icon": "📢", "desc": "Пригласить 1 друга"},
    "referral_5":          {"name": "Рекрутёр",          "icon": "👥", "desc": "Пригласить 5 друзей"},
    # ── Крафт ─────────────────────────────────────────────────────────────────
    "first_craft":         {"name": "Кузнец",            "icon": "⚗️", "desc": "Первый крафт"},
    "craft_legendary":     {"name": "Алхимик",           "icon": "🔮", "desc": "Скрафтить легендарную"},
    "crafts_10":           {"name": "Мастер крафта",     "icon": "🧪", "desc": "10 крафтов"},
    # ── Рынок ─────────────────────────────────────────────────────────────────
    "first_market_sell":   {"name": "Торговец рынка",    "icon": "🏪", "desc": "Продать карточку на рынке"},
    "first_market_buy":    {"name": "Покупатель",        "icon": "🛍", "desc": "Купить карточку на рынке"},
    "market_deals_10":     {"name": "Деловой человек",   "icon": "💼", "desc": "10 сделок на рынке"},
    # ── Особые ────────────────────────────────────────────────────────────────
    "featured_card":       {"name": "Везунчик",          "icon": "🍀", "desc": "Выбить карту дня из чата"},
    "wishlist_found":      {"name": "Мечтатель",         "icon": "💭", "desc": "Найти карту из вишлиста"},
}


def _check_condition(user, ach_id: str, cards: dict) -> bool:
    """Возвращает True, если условие достижения выполнено."""
    total_cards  = sum(user.cards.values()) if user.cards else 0
    unique_cards = len(user.cards)
    wins = user.game_stats.total_wins() if hasattr(user, 'game_stats') else 0

    has_legendary = any(
        cards.get(cid) and cards[cid].rarity == "legendary"
        for cid in user.cards
    )
    has_vinyl = any(
        cards.get(cid) and cards[cid].rarity == "vinyl figure"
        for cid in user.cards
    )

    streak      = getattr(user, 'daily_streak', 0)
    total_trades = getattr(user, 'total_trades', 0)
    total_gifts  = getattr(user, 'total_gifts', 0)
    total_crafts = getattr(user, 'total_crafts', 0)
    crafted_leg  = getattr(user, 'total_crafted_legendary', 0)
    sold         = getattr(user, 'market_sold_count', 0)
    bought       = getattr(user, 'market_bought_count', 0)
    referrals    = len(getattr(user, 'referrals', []))

    rules = {
        "first_card":        total_cards >= 1,
        "first_legendary":   has_legendary,
        "first_vinyl":       has_vinyl,
        "cards_10":          total_cards >= 10,
        "cards_50":          total_cards >= 50,
        "cards_100":         user.opened_packs >= 100,
        "unique_20":         unique_cards >= 20,
        "unique_50":         unique_cards >= 50,
        "streak_3":          streak >= 3,
        "streak_7":          streak >= 7,
        "streak_30":         streak >= 30,
        "first_win":         wins >= 1,
        "wins_10":           wins >= 10,
        "wins_50":           wins >= 50,
        "wins_100":          wins >= 100,
        "level_5":           user.level >= 5,
        "level_10":          user.level >= 10,
        "level_25":          user.level >= 25,
        "level_50":          user.level >= 50,
        "first_trade":       total_trades >= 1,
        "trades_10":         total_trades >= 10,
        "first_gift":        total_gifts >= 1,
        "gifts_5":           total_gifts >= 5,
        "referral_1":        referrals >= 1,
        "referral_5":        referrals >= 5,
        "first_craft":       total_crafts >= 1,
        "craft_legendary":   crafted_leg >= 1,
        "crafts_10":         total_crafts >= 10,
        "first_market_sell": sold >= 1,
        "first_market_buy":  bought >= 1,
        "market_deals_10":   (sold + bought) >= 10,
        # Эти выдаются вручную при событии:
        "featured_card":     "featured_card" in getattr(user, 'achievements', {}),
        "wishlist_found":    "wishlist_found" in getattr(user, 'achievements', {}),
    }
    return rules.get(ach_id, False)


async def check_and_award_achievements(user, bot, cards: dict, save_fn) -> None:
    """
    Проверяет все достижения пользователя и отправляет уведомление о новых.
    Вызывать после любого значимого события (открытие карты, крафт, победа).
    """
    if not hasattr(user, 'achievements'):
        user.achievements = {}

    newly_unlocked = []
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in user.achievements:
            continue
        if _check_condition(user, ach_id, cards):
            user.achievements[ach_id] = datetime.now().isoformat()
            newly_unlocked.append(ach)

    if not newly_unlocked:
        return

    save_fn()
    lines = ["🏅 <b>Новые достижения!</b>\n"]
    for ach in newly_unlocked:
        lines.append(f"{ach['icon']} <b>{ach['name']}</b> — {ach['desc']}")
    try:
        await bot.send_message(user.user_id, "\n".join(lines))
    except Exception as e:
        logger.error(f"Ошибка уведомления достижений ({user.user_id}): {e}")


def award_achievement_manual(user, ach_id: str) -> bool:
    """Выдать достижение вручную (для featured_card, wishlist_found)."""
    if not hasattr(user, 'achievements'):
        user.achievements = {}
    if ach_id not in user.achievements:
        user.achievements[ach_id] = datetime.now().isoformat()
        return True
    return False


def format_achievements_page(user) -> str:
    """Возвращает текст страницы достижений для профиля."""
    if not hasattr(user, 'achievements') or not user.achievements:
        return "🏅 <b>Достижения</b>\n\nПока нет разблокированных достижений.\nОткройте карточку, чтобы начать!"

    unlocked = user.achievements
    total = len(ACHIEVEMENTS)
    done  = len(unlocked)

    lines = [f"🏅 <b>Достижения ({done}/{total})</b>\n"]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            date_str = unlocked[ach_id][:10]
            lines.append(f"✅ {ach['icon']} <b>{ach['name']}</b> — {ach['desc']} <i>({date_str})</i>")
        else:
            lines.append(f"🔒 {ach['icon']} {ach['name']} — {ach['desc']}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════════
# 4. УМНЫЕ НАПОМИНАНИЯ О КУЛДАУНЕ
# ════════════════════════════════════════════════════════════════════════════════
async def notify_cooldown_ready(users: dict, bot, save_fn, get_card_cooldown_hours_fn=None) -> None:
    """
    Вызывать из periodic_tasks каждые 15 минут.
    Отправляет уведомление пользователям, у которых только что истёк кулдаун.
    """
    now = datetime.now()
    notified = 0

    for user in users.values():
        if user.is_banned or user.is_frozen:
            continue
        # Пользователь отключил уведомления
        if hasattr(user, 'notification_settings') and not user.notification_settings.card_available:
            continue
        # Уведомление уже отправлено
        if getattr(user, 'cooldown_notified', False):
            continue
        # Кулдаун ещё не начинался
        if not user.last_card_time:
            continue

        # Используем переданную функцию или стандартный расчёт
        if get_card_cooldown_hours_fn:
            cd_hours = get_card_cooldown_hours_fn(user)
        else:
            cd_hours = 2 if (user.has_reduced_cd and user.reduced_cd_until
                             and datetime.fromisoformat(user.reduced_cd_until) > now) else 4
        
        ready_at = datetime.fromisoformat(user.last_card_time) + timedelta(hours=cd_hours)

        if now >= ready_at:
            try:
                streak = getattr(user, 'daily_streak', 0)
                streak_hint = ""
                if streak > 0:
                    next_bonus = STREAK_REWARDS.get(min(streak + 1, 7), STREAK_MAX_BONUS)
                    streak_hint = (
                        f"\n{streak_emoji(streak)} Стрик: {streak} дней подряд "
                        f"| Бонус завтра: +{next_bonus}🎫"
                    )
                await bot.send_message(
                    user.user_id,
                    f"⏰ <b>Карточка готова!</b>\n\n"
                    f"Напишите <b>фанко</b> в групповом чате.{streak_hint}"
                )
                user.cooldown_notified = True
                notified += 1
                import asyncio
                await asyncio.sleep(0.05)
            except Exception:
                pass

    if notified:
        save_fn()
        logger.info(f"🔔 Напоминаний о кулдауне: {notified}")
