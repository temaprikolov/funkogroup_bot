# events.py — Еженедельные ивенты и реферальный конкурс
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, TYPE_CHECKING

from config import WEEKLY_EVENT_TYPES, WEEKLY_EVENT_PRIZES, REFERRAL_CONTEST_PRIZES

if TYPE_CHECKING:
    from models import WeeklyEvent, ReferralContest, User

logger = logging.getLogger(__name__)

# Ссылки на глобальные данные (устанавливаются из main.py)
bot = None
users = None
cards = None
save_data = None
add_premium = None
current_weekly_event: Optional['WeeklyEvent'] = None
current_referral_contest: Optional['ReferralContest'] = None


EVENT_NAMES = {
    "open_cards":         "🎴 Открой больше всего карточек",
    "collect_legendaries": "🟡 Собери больше всего легендарок",
    "win_games":          "🏆 Выиграй больше всего игр",
    "collect_tokens":     "🎫 Накопи больше всего токенов",
}


def setup_events(bot_i, users_d, cards_d, save_fn, add_premium_fn,
                 weekly_ev, referral_cont):
    global bot, users, cards, save_data, add_premium
    global current_weekly_event, current_referral_contest
    bot = bot_i
    users = users_d
    cards = cards_d
    save_data = save_fn
    add_premium = add_premium_fn
    current_weekly_event = weekly_ev
    current_referral_contest = referral_cont


def get_current_event() -> Optional['WeeklyEvent']:
    return current_weekly_event


def get_current_contest() -> Optional['ReferralContest']:
    return current_referral_contest


def add_event_score(user_id: int, event_type: str, amount: int = 1):
    """Добавить очки пользователю в текущем ивенте."""
    global current_weekly_event
    if not current_weekly_event:
        return
    if current_weekly_event.event_type != event_type:
        return
    if datetime.fromisoformat(current_weekly_event.end_time) < datetime.now():
        return
    current_weekly_event.add_score(user_id, amount)


def new_weekly_event() -> 'WeeklyEvent':
    from models import WeeklyEvent
    etype = random.choice(WEEKLY_EVENT_TYPES)
    now = datetime.now()
    ev = WeeklyEvent(
        event_id=f"ev_{int(now.timestamp())}",
        event_type=etype,
        start_time=now.isoformat(),
        end_time=(now + timedelta(days=7)).isoformat(),
    )
    return ev


def new_referral_contest(season: int) -> 'ReferralContest':
    from models import ReferralContest
    now = datetime.now()
    # Заканчивается в конце текущего месяца
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return ReferralContest(season, now.isoformat(), end.isoformat())


async def check_and_rotate_weekly_event():
    """Проверить не истёк ли ивент, раздать призы, создать новый."""
    global current_weekly_event
    if not current_weekly_event:
        current_weekly_event = new_weekly_event()
        save_data()
        return
    end = datetime.fromisoformat(current_weekly_event.end_time)
    if datetime.now() < end:
        return
    if not current_weekly_event.prizes_distributed:
        await distribute_weekly_prizes()
    current_weekly_event = new_weekly_event()
    save_data()
    logger.info(f"🎉 Новый еженедельный ивент: {current_weekly_event.event_type}")


async def distribute_weekly_prizes():
    global current_weekly_event
    if not current_weekly_event or current_weekly_event.prizes_distributed:
        return
    top = current_weekly_event.get_top(5)
    logger.info(f"Раздаём призы еженедельного ивента '{current_weekly_event.event_type}', топ: {len(top)}")
    for rank, (uid, score) in enumerate(top, 1):
        if rank > 5:
            break
        prize = WEEKLY_EVENT_PRIZES.get(rank)
        if not prize:
            continue
        user = users.get(uid)
        if not user:
            continue
        user.tokens += prize["tokens"]
        if prize.get("premium_days"):
            add_premium(user, prize["premium_days"])
        if prize.get("extra") == "skip_both":
            user.skip_card_cooldown_available = True
            user.skip_trade_cooldown_available = True
        # Уведомление
        try:
            ev_name = EVENT_NAMES.get(current_weekly_event.event_type, "ивент")
            await bot.send_message(
                uid,
                f"🎉 <b>Ивент завершён!</b>\n\n"
                f"📋 {ev_name}\n"
                f"🏅 Место: <b>{rank}</b>\n"
                f"📊 Очков: {score}\n\n"
                f"🎁 <b>Ваш приз:</b>\n"
                f"• +{prize['tokens']} токенов\n" +
                (f"• Премиум {prize['premium_days']} дней\n" if prize.get("premium_days") else "") +
                (f"• Скип кулдауна карточки и обмена\n" if prize.get("extra") == "skip_both" else "")
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления о призе: {e}")
    current_weekly_event.prizes_distributed = True
    save_data()


async def check_and_rotate_referral_contest():
    """Проверить не истёк ли конкурс, раздать призы, создать новый."""
    global current_referral_contest
    if not current_referral_contest:
        current_referral_contest = new_referral_contest(1)
        save_data()
        return
    end = datetime.fromisoformat(current_referral_contest.end_time)
    if datetime.now() < end:
        return
    if not current_referral_contest.prizes_distributed:
        await distribute_referral_prizes()
    new_season = current_referral_contest.season + 1
    current_referral_contest = new_referral_contest(new_season)
    # Сбрасываем месячные рефералы
    for u in users.values():
        u.referral_contest_month_refs = 0
    save_data()
    logger.info(f"🏆 Новый сезон реферального конкурса: {new_season}")


def get_referral_contest_top(limit: int = 10):
    """Топ участников текущего конкурса."""
    ranked = []
    for u in users.values():
        if u.is_banned or u.is_frozen:
            continue
        refs = u.referral_contest_month_refs
        if refs > 0:
            ranked.append((u.user_id, refs))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:limit]


async def distribute_referral_prizes():
    global current_referral_contest
    if not current_referral_contest or current_referral_contest.prizes_distributed:
        return
    top = get_referral_contest_top(10)
    logger.info(f"Раздаём призы реферального конкурса сезон {current_referral_contest.season}, топ: {len(top)}")

    for rank, (uid, refs_count) in enumerate(top, 1):
        if rank > 10:
            break
        prize_key = rank if rank <= 3 else "4-10"
        prize = REFERRAL_CONTEST_PRIZES.get(prize_key)
        if not prize:
            continue
        user = users.get(uid)
        if not user:
            continue
        # Пропустить если уже получали приз в этом сезоне
        if user.referral_contest_season >= current_referral_contest.season:
            continue
        user.tokens += prize["tokens"]
        if prize.get("premium_days"):
            add_premium(user, prize["premium_days"])
        if prize.get("skips"):
            user.skip_card_cooldown_available = True
            user.skip_trade_cooldown_available = True
        # Виниловые карточки
        if prize.get("vinyl_cards"):
            vinyl_cards = [cid for cid, c in cards.items() if c.rarity == "vinyl figure"]
            for _ in range(prize["vinyl_cards"]):
                if vinyl_cards:
                    cid = random.choice(vinyl_cards)
                    user.cards[cid] = user.cards.get(cid, 0) + 1
        # Легендарные карточки
        if prize.get("legendary_cards"):
            leg_cards = [cid for cid, c in cards.items() if c.rarity == "legendary"]
            for _ in range(prize["legendary_cards"]):
                if leg_cards:
                    cid = random.choice(leg_cards)
                    user.cards[cid] = user.cards.get(cid, 0) + 1

        user.referral_contest_season = current_referral_contest.season
        prize_lines = [f"• +{prize['tokens']} токенов"]
        if prize.get("premium_days"):
            prize_lines.append(f"• Премиум {prize['premium_days']} дней")
        if prize.get("skips"):
            prize_lines.append(f"• Скип кулдауна карточки и обмена")
        if prize.get("vinyl_cards"):
            prize_lines.append(f"• {prize['vinyl_cards']}x Виниловая фигурка")
        if prize.get("legendary_cards"):
            prize_lines.append(f"• {prize['legendary_cards']}x Легендарная карточка")

        try:
            await bot.send_message(
                uid,
                f"🏆 <b>Реферальный конкурс завершён!</b>\n\n"
                f"🥇 Ваше место: <b>{rank}</b>\n"
                f"👥 Приглашено за месяц: {refs_count}\n\n"
                f"🎁 <b>Ваши призы:</b>\n" + "\n".join(prize_lines)
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления реф-конкурса: {e}")

    current_referral_contest.prizes_distributed = True
    save_data()
