# market_handlers.py — Токен-аукцион (открытый рынок карточек)
import random
import logging
from datetime import datetime

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from models import MarketListing, MARKET_FEE_PCT, MARKET_LISTING_DAYS, MARKET_MIN_PRICE, MARKET_MAX_PRICE

logger = logging.getLogger(__name__)
market_router = Router()
router = market_router


# ─── Глобальные переменные (устанавливаются через setup) ─────────────────────
bot = None
users = None
cards = None
market_listings = None
save_data = None
get_or_create_user = None
get_rarity_color = None
get_rarity_name = None
check_access_before_handle = None
check_and_award_achievements = None


class MarketStates(StatesGroup):
    selecting_card  = State()
    entering_price  = State()


def setup_market_handlers(bot_i, users_d, cards_d, listings_d, save_fn,
                          get_user_fn, rarity_color_fn, rarity_name_fn,
                          access_fn, achievements_fn=None):
    global bot, users, cards, market_listings, save_data
    global get_or_create_user, get_rarity_color, get_rarity_name
    global check_access_before_handle, check_and_award_achievements
    bot = bot_i; users = users_d; cards = cards_d; market_listings = listings_d
    save_data = save_fn; get_or_create_user = get_user_fn
    get_rarity_color = rarity_color_fn; get_rarity_name = rarity_name_fn
    check_access_before_handle = access_fn
    check_and_award_achievements = achievements_fn


# ════════════════════════════════════════════════════════════════════════════════
# Вспомогательные функции
# ════════════════════════════════════════════════════════════════════════════════
def _clean_expired():
    """Истёкшие лоты — снять, вернуть карточки продавцам."""
    changed = False
    for listing in list(market_listings.values()):
        if listing.is_active and listing.is_expired():
            listing.is_active = False
            seller = users.get(listing.seller_id)
            if seller:
                seller.cards[listing.card_id] = seller.cards.get(listing.card_id, 0) + 1
            changed = True
    if changed:
        save_data()


def clean_expired_market():
    """Публичная обёртка для _clean_expired (вызывается из periodic_tasks)"""
    _clean_expired()


def _active_listings(exclude_user_id: int = None):
    return [
        (lid, l) for lid, l in market_listings.items()
        if l.is_active and not l.is_expired()
        and (exclude_user_id is None or l.seller_id != exclude_user_id)
    ]


def _sort_key_price(item):
    return item[1].price_tokens


# ════════════════════════════════════════════════════════════════════════════════
# Главное меню рынка
# ════════════════════════════════════════════════════════════════════════════════
@router.message(F.text == "🏪 Рынок")
async def market_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    _clean_expired()
    user = get_or_create_user(message.from_user.id)

    active = _active_listings(exclude_user_id=user.user_id)
    my     = [l for l in market_listings.values()
              if l.is_active and l.seller_id == user.user_id]

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=f"🛍 Купить ({len(active)} лотов)", callback_data="mkt_browse_0"))
    kb.add(InlineKeyboardButton(text="📤 Выставить карточку",            callback_data="mkt_sell_start"))
    kb.add(InlineKeyboardButton(text=f"📋 Мои лоты ({len(my)})",         callback_data="mkt_my"))
    kb.add(InlineKeyboardButton(text="🔙 Назад",                         callback_data="back_to_menu"))
    kb.adjust(1)

    await message.answer(
        f"🏪 <b>Токен-рынок</b>\n\n"
        f"Покупайте и продавайте карточки за токены!\n\n"
        f"💰 Ваш баланс: {user.tokens}🎫\n"
        f"📊 Активных лотов: {len(active)}\n"
        f"💸 Комиссия продавца: {MARKET_FEE_PCT}%\n"
        f"⏱ Лот активен: {MARKET_LISTING_DAYS} дня",
        reply_markup=kb.as_markup()
    )


# ════════════════════════════════════════════════════════════════════════════════
# Просмотр лотов (постраничный)
# ════════════════════════════════════════════════════════════════════════════════
PAGE_SIZE = 10

@router.callback_query(lambda c: c.data.startswith("mkt_browse_"))
async def mkt_browse(callback: types.CallbackQuery):
    _clean_expired()
    user  = get_or_create_user(callback.from_user.id)
    page  = int(callback.data.replace("mkt_browse_", ""))
    items = sorted(_active_listings(exclude_user_id=user.user_id), key=_sort_key_price)

    if not items:
        await callback.answer("🏪 Рынок пуст — будьте первым!", show_alert=True)
        return

    start = page * PAGE_SIZE
    end   = min(start + PAGE_SIZE, len(items))
    total_pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE

    kb = InlineKeyboardBuilder()
    for lid, listing in items[start:end]:
        card   = cards.get(listing.card_id)
        if not card:
            continue
        seller = users.get(listing.seller_id)
        sname  = f"@{seller.username}" if seller else "?"
        icon   = get_rarity_color(card.rarity)
        kb.add(InlineKeyboardButton(
            text=f"{icon} {card.name} — {listing.price_tokens}🎫 ({sname})",
            callback_data=f"mkt_view_{lid}"
        ))
    kb.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mkt_browse_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mkt_browse_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="mkt_back"))
    kb.adjust(1)

    await callback.message.edit_text(
        f"🛍 <b>Лоты ({start+1}–{end} из {len(items)})</b>\n"
        f"💰 Ваш баланс: {user.tokens}🎫",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "mkt_back")
async def mkt_back(callback: types.CallbackQuery):
    # BUG FIX: market_menu() is a message handler — calling it with callback.message
    # fails because callback.message.from_user is the bot, not the user.
    # Re-build and send the market menu manually.
    _clean_expired()
    user = get_or_create_user(callback.from_user.id)
    active = _active_listings(exclude_user_id=user.user_id)
    my     = [l for l in market_listings.values()
              if l.is_active and l.seller_id == user.user_id]
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=f"🛍 Купить ({len(active)} лотов)", callback_data="mkt_browse_0"))
    kb.add(InlineKeyboardButton(text="📤 Выставить карточку",            callback_data="mkt_sell_start"))
    kb.add(InlineKeyboardButton(text=f"📋 Мои лоты ({len(my)})",         callback_data="mkt_my"))
    kb.add(InlineKeyboardButton(text="🔙 Назад",                         callback_data="back_to_menu"))
    kb.adjust(1)
    try:
        await callback.message.edit_text(
            f"🏪 <b>Токен-рынок</b>\n\n"
            f"💰 Ваш баланс: {user.tokens}🎫\n"
            f"📊 Активных лотов: {len(active)}\n"
            f"💸 Комиссия продавца: {MARKET_FEE_PCT}%\n"
            f"⏱ Лот активен: {MARKET_LISTING_DAYS} дня",
            reply_markup=kb.as_markup()
        )
    except Exception:
        await callback.message.answer(
            f"🏪 <b>Токен-рынок</b>\n\n💰 Баланс: {user.tokens}🎫",
            reply_markup=kb.as_markup()
        )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Просмотр конкретного лота
# ════════════════════════════════════════════════════════════════════════════════
@router.callback_query(lambda c: c.data.startswith("mkt_view_"))
async def mkt_view(callback: types.CallbackQuery):
    lid     = callback.data.replace("mkt_view_", "")
    listing = market_listings.get(lid)
    if not listing or not listing.is_active or listing.is_expired():
        await callback.answer("❌ Лот уже недоступен", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id)
    card = cards.get(listing.card_id)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return

    seller = users.get(listing.seller_id)
    sname  = f"@{seller.username}" if seller else "Неизвестно"
    expires = datetime.fromisoformat(listing.expires_at)
    h_left  = max(0, int((expires - datetime.now()).total_seconds() // 3600))

    kb = InlineKeyboardBuilder()
    if user.user_id != listing.seller_id:
        kb.add(InlineKeyboardButton(
            text=f"💸 Купить за {listing.price_tokens}🎫",
            callback_data=f"mkt_buy_{lid}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 К списку", callback_data="mkt_browse_0"))
    kb.adjust(1)

    await callback.message.edit_text(
        f"{get_rarity_color(card.rarity)} <b>{card.name}</b>\n"
        f"📊 {get_rarity_name(card.rarity)}\n\n"
        f"💰 Цена: <b>{listing.price_tokens}🎫</b>\n"
        f"👤 Продавец: {sname}\n"
        f"⏱ Истекает через: {h_left} ч.\n\n"
        f"Ваш баланс: {user.tokens}🎫",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════════════════
# Покупка лота
# ════════════════════════════════════════════════════════════════════════════════
@router.callback_query(lambda c: c.data.startswith("mkt_buy_"))
async def mkt_buy(callback: types.CallbackQuery):
    lid     = callback.data.replace("mkt_buy_", "")
    listing = market_listings.get(lid)
    if not listing or not listing.is_active or listing.is_expired():
        await callback.answer("❌ Лот уже недоступен", show_alert=True)
        return

    buyer = get_or_create_user(callback.from_user.id)
    if buyer.user_id == listing.seller_id:
        await callback.answer("❌ Нельзя купить свой лот", show_alert=True)
        return
    if buyer.tokens < listing.price_tokens:
        await callback.answer(
            f"❌ Нужно {listing.price_tokens}🎫, у вас {buyer.tokens}🎫",
            show_alert=True
        )
        return

    card = cards.get(listing.card_id)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return

    # ── Провести сделку ───────────────────────────────────────────────────────
    fee        = max(1, listing.price_tokens * MARKET_FEE_PCT // 100)
    seller_gets = listing.price_tokens - fee

    buyer.tokens -= listing.price_tokens
    buyer.cards[listing.card_id] = buyer.cards.get(listing.card_id, 0) + 1
    buyer.market_bought_count   = getattr(buyer, 'market_bought_count', 0) + 1

    seller = users.get(listing.seller_id)
    if seller:
        seller.tokens += seller_gets
        seller.market_sold_count = getattr(seller, 'market_sold_count', 0) + 1

    listing.is_active = False
    save_data()

    # ── Достижения ────────────────────────────────────────────────────────────
    if check_and_award_achievements:
        await check_and_award_achievements(buyer, bot, cards, save_data)
        if seller:
            await check_and_award_achievements(seller, bot, cards, save_data)

    icon = get_rarity_color(card.rarity)
    await callback.message.edit_text(
        f"✅ <b>Покупка совершена!</b>\n\n"
        f"{icon} <b>{card.name}</b>\n"
        f"💸 Потрачено: {listing.price_tokens}🎫\n"
        f"Остаток: {buyer.tokens}🎫\n\n"
        f"Карточка добавлена в инвентарь!"
    )
    await callback.answer()

    if seller:
        try:
            await bot.send_message(
                seller.user_id,
                f"✅ <b>Ваш лот продан!</b>\n\n"
                f"{icon} {card.name}\n"
                f"💰 Выручка: {seller_gets}🎫 (−{fee}🎫 комиссия)\n"
                f"Покупатель: @{buyer.username}"
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════════
# Выставить карточку
# ════════════════════════════════════════════════════════════════════════════════
@router.callback_query(lambda c: c.data == "mkt_sell_start")
async def mkt_sell_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id)

    sellable = [
        (cid, qty) for cid, qty in user.cards.items()
        if qty >= 1 and cards.get(cid)
    ]
    if not sellable:
        await callback.answer("❌ Нет карточек для продажи", show_alert=True)
        return

    sellable.sort(key=lambda x: (cards[x[0]].rarity, x[1]), reverse=True)

    kb = InlineKeyboardBuilder()
    for cid, qty in sellable[:20]:
        card = cards[cid]
        icon = get_rarity_color(card.rarity)
        # BUG FIX: warn user if this is their only copy of a card
        last_copy_warn = " ⚠️ последняя" if qty == 1 else ""
        kb.add(InlineKeyboardButton(
            text=f"{icon} {card.name} (x{qty}){last_copy_warn}",
            callback_data=f"mkt_pick_{cid}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="mkt_back"))
    kb.adjust(1)

    await callback.message.edit_text(
        "📤 <b>Выберите карточку для продажи:</b>",
        reply_markup=kb.as_markup()
    )
    await state.set_state(MarketStates.selecting_card)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("mkt_pick_"), MarketStates.selecting_card)
async def mkt_pick_card(callback: types.CallbackQuery, state: FSMContext):
    cid  = callback.data.replace("mkt_pick_", "")
    card = cards.get(cid)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return

    await state.update_data(sell_card_id=cid)
    icon = get_rarity_color(card.rarity)
    fee_example = max(1, 100 * MARKET_FEE_PCT // 100)

    await callback.message.edit_text(
        f"💰 <b>Установите цену</b>\n\n"
        f"{icon} {card.name} ({get_rarity_name(card.rarity)})\n\n"
        f"Введите цену в 🎫 токенах ({MARKET_MIN_PRICE}–{MARKET_MAX_PRICE}):\n"
        f"<i>Комиссия {MARKET_FEE_PCT}% при продаже (пример: 100🎫 → вы получите {100-fee_example}🎫)</i>"
    )
    await state.set_state(MarketStates.entering_price)
    await callback.answer()


@router.message(MarketStates.entering_price, F.text)
async def mkt_enter_price(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id):
        return

    try:
        price = int(message.text.strip())
        if not (MARKET_MIN_PRICE <= price <= MARKET_MAX_PRICE):
            raise ValueError
    except ValueError:
        await message.answer(f"❌ Введите число от {MARKET_MIN_PRICE} до {MARKET_MAX_PRICE}")
        return

    data = await state.get_data()
    cid  = data.get('sell_card_id')
    user = get_or_create_user(message.from_user.id)
    card = cards.get(cid)

    if not card or user.cards.get(cid, 0) < 1:
        await message.answer("❌ Карточка недоступна")
        await state.clear()
        return

    # Снимаем карточку с инвентаря
    user.cards[cid] = user.cards.get(cid, 0) - 1
    if user.cards[cid] <= 0:
        del user.cards[cid]

    lid = f"lot_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    market_listings[lid] = MarketListing(lid, user.user_id, cid, price)
    # BUG FIX: market_sold_count should only increment when the card is actually SOLD,
    # not when the listing is created. Removed the premature increment here.
    save_data()

    if check_and_award_achievements:
        await check_and_award_achievements(user, bot, cards, save_data)

    icon = get_rarity_color(card.rarity)
    fee  = max(1, price * MARKET_FEE_PCT // 100)
    await message.answer(
        f"✅ <b>Лот выставлен!</b>\n\n"
        f"{icon} {card.name}\n"
        f"💰 Цена: {price}🎫\n"
        f"💸 Вы получите: {price - fee}🎫 (−{fee}🎫 комиссия)\n"
        f"⏱ Активен {MARKET_LISTING_DAYS} дня\n\n"
        f"🆔 <code>{lid}</code>"
    )
    await state.clear()


# ════════════════════════════════════════════════════════════════════════════════
# Мои лоты
# ════════════════════════════════════════════════════════════════════════════════
@router.callback_query(lambda c: c.data == "mkt_my")
async def mkt_my_listings(callback: types.CallbackQuery):
    _clean_expired()
    user = get_or_create_user(callback.from_user.id)
    my   = [(lid, l) for lid, l in market_listings.items()
            if l.seller_id == user.user_id and l.is_active and not l.is_expired()]

    if not my:
        await callback.answer("У вас нет активных лотов", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for lid, listing in my:
        card = cards.get(listing.card_id)
        if not card:
            continue
        icon = get_rarity_color(card.rarity)
        kb.add(InlineKeyboardButton(
            text=f"{icon} {card.name} — {listing.price_tokens}🎫  ✖ Снять",
            callback_data=f"mkt_cancel_{lid}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="mkt_back"))
    kb.adjust(1)

    await callback.message.edit_text(
        "📋 <b>Ваши лоты</b>\n\nНажмите чтобы снять с продажи:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("mkt_cancel_"))
async def mkt_cancel(callback: types.CallbackQuery):
    lid     = callback.data.replace("mkt_cancel_", "")
    listing = market_listings.get(lid)
    user    = get_or_create_user(callback.from_user.id)

    if not listing or listing.seller_id != user.user_id:
        await callback.answer("❌ Лот не найден", show_alert=True)
        return

    listing.is_active = False
    user.cards[listing.card_id] = user.cards.get(listing.card_id, 0) + 1
    save_data()

    card = cards.get(listing.card_id)
    name = card.name if card else listing.card_id
    await callback.answer(f"✅ Лот снят, {name} возвращена", show_alert=True)

    # Обновить список
    remaining = [(lid2, l) for lid2, l in market_listings.items()
                 if l.seller_id == user.user_id and l.is_active and not l.is_expired()]
    if remaining:
        await mkt_my_listings(callback)
    else:
        await callback.message.delete()
