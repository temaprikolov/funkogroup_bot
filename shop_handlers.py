# shop_handlers.py — Магазин, эксклюзивы, лутбоксы, подарки (ИСПРАВЛЕНО)
import random
import logging
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import *
from models import Order

shop_router = Router()
router = shop_router   # ← КРИТИЧЕСКИЙ ФИКС

logger = logging.getLogger(__name__)

# ─── Глобальные переменные ───
bot = None
users = None
cards = None
shop_items = None
orders = None
exclusive_cards = None
save_data = None
get_or_create_user = None
check_access_before_handle = None
check_subscription = None
get_level_discount = None
get_price_with_discount = None
get_token_price = None
get_rarity_color = None
get_rarity_name = None
update_shop = None
update_user_interaction = None
show_payment_methods = None
create_order = None


def setup_shop_handlers(bot_i, users_d, cards_d, shop_d, orders_d, excl_d,
                        save_fn, get_user_fn, access_fn, sub_fn,
                        level_disc_fn, price_disc_fn, token_price_fn,
                        rarity_color_fn, rarity_name_fn,
                        update_shop_fn, update_user_fn, payment_fn,
                        create_order_fn=None):
    global bot, users, cards, shop_items, orders, exclusive_cards, save_data
    global get_or_create_user, check_access_before_handle, check_subscription
    global get_level_discount, get_price_with_discount, get_token_price
    global get_rarity_color, get_rarity_name, update_shop, update_user_interaction
    global show_payment_methods, create_order
    bot = bot_i; users = users_d; cards = cards_d; shop_items = shop_d
    orders = orders_d; exclusive_cards = excl_d; save_data = save_fn
    get_or_create_user = get_user_fn; check_access_before_handle = access_fn
    check_subscription = sub_fn; get_level_discount = level_disc_fn
    get_price_with_discount = price_disc_fn; get_token_price = token_price_fn
    get_rarity_color = rarity_color_fn; get_rarity_name = rarity_name_fn
    update_shop = update_shop_fn; update_user_interaction = update_user_fn
    show_payment_methods = payment_fn; create_order = create_order_fn


# ══════════════════════════════════════════
# Вспомогательная функция — строка товара
# ══════════════════════════════════════════
def _shop_item_line(card_id, item, user_level, discount):
    if card_id.startswith('skip_card_cooldown'):
        tp = get_token_price(item.price)
        hours_left = max(0, int((datetime.fromisoformat(item.expires_at) - datetime.now()).total_seconds() // 3600))
        return f"⚡ Скип кулдауна карточки — {item.price}₽ / {tp}🎫 ({hours_left}ч)"
    if card_id.startswith('skip_trade_cooldown'):
        tp = get_token_price(item.price)
        hours_left = max(0, int((datetime.fromisoformat(item.expires_at) - datetime.now()).total_seconds() // 3600))
        return f"🔄 Скип кулдауна обменов — {item.price}₽ / {tp}🎫 ({hours_left}ч)"
    card = cards.get(card_id)
    if not card:
        return f"Неизвестный товар ({card_id})"
    hours_left = max(0, int((datetime.fromisoformat(item.expires_at) - datetime.now()).total_seconds() // 3600))
    disc_price = get_price_with_discount(item.price, user_level)
    tp = get_token_price(item.price)
    icon = get_rarity_color(card.rarity)
    # Флэш-скидка
    flash_label = ""
    if hasattr(item, 'flash_sale_until') and item.flash_sale_until:
        if datetime.fromisoformat(item.flash_sale_until) > datetime.now():
            flash_label = " 🔥ФЛЭШ"
    price_text = f"{disc_price}₽" if discount > 0 else f"{item.price}₽"
    return f"{icon}{flash_label} {card.name} — {price_text} / {tp}🎫 ({hours_left}ч)"


def _build_shop_keyboard(user):
    discount = get_level_discount(user.level)
    keyboard = InlineKeyboardBuilder()
    for card_id, item in shop_items.items():
        label = _shop_item_line(card_id, item, user.level, discount)
        keyboard.add(InlineKeyboardButton(text=label, callback_data=f"shop_buy_tokens_{card_id}"))
    keyboard.add(InlineKeyboardButton(text="📦 Лутбоксы", callback_data="shop_lootboxes"))
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="shop_refresh"))
    keyboard.add(InlineKeyboardButton(text="❓ Помощь", callback_data="shop_help"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    keyboard.adjust(1)
    return keyboard.as_markup()


# ══════════════════════════════════════════
# Магазин
# ══════════════════════════════════════════
@router.message(F.text == "🛒 Магазин")
async def shop_menu_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    # Подписка проверяется при /start
    update_shop()
    user = get_or_create_user(message.from_user.id)
    discount = get_level_discount(user.level)
    disc_text = f"\n🎁 Ваша скидка за ур.{user.level}: {discount}%" if discount else ""
    secret_btn_text = ""
    if hasattr(user, 'secret_shop_expires') and user.secret_shop_expires:
        if datetime.fromisoformat(user.secret_shop_expires) > datetime.now():
            secret_btn_text = "\n🤫 <b>У вас есть доступ в Секретный магазин!</b>"

    await message.answer(
        f"🛒 <b>Магазин карточек</b>\n\n"
        f"💰 Токенов: {user.tokens}🎫{disc_text}{secret_btn_text}\n\n"
        f"<b>Карточки (₽ / 🎫):</b>",
        reply_markup=_build_shop_keyboard(user)
    )
    user.last_shop_check = datetime.now().isoformat()
    save_data()


@router.callback_query(lambda c: c.data == "shop_refresh")
async def shop_refresh_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id):
        return
    update_shop()
    user = get_or_create_user(callback.from_user.id)
    discount = get_level_discount(user.level)
    disc_text = f"\n🎁 Скидка {discount}%" if discount else ""
    try:
        await callback.message.edit_text(
            f"🛒 <b>Магазин (обновлено)</b>\n\n💰 Токенов: {user.tokens}🎫{disc_text}",
            reply_markup=_build_shop_keyboard(user)
        )
    except Exception:
        pass
    await callback.answer("🛒 Обновлено!")


# ══════════════════════════════════════════
# Выбор оплаты товара
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data.startswith("shop_buy_tokens_"))
async def shop_buy_select_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("shop_buy_tokens_", "")
    if card_id not in shop_items:
        await callback.answer("❌ Товар уже куплен!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    item = shop_items[card_id]
    tp = get_token_price(item.price)
    dp = get_price_with_discount(item.price, user.level)

    if card_id.startswith('skip_card_cooldown'):
        name = "⚡ Скип кулдауна карточки"
    elif card_id.startswith('skip_trade_cooldown'):
        name = "🔄 Скип кулдауна обменов"
    else:
        card = cards.get(card_id)
        name = f"{get_rarity_color(card.rarity)} {card.name}" if card else card_id

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f"💳 За рубли ({dp}₽)", callback_data=f"shop_buy_rubles_{card_id}"))
    keyboard.add(InlineKeyboardButton(text=f"🎫 За токены ({tp}🎫)", callback_data=f"shop_buy_token_confirm_{card_id}"))
    keyboard.add(InlineKeyboardButton(text=f"🎁 В подарок", callback_data=f"shop_gift_{card_id}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="shop_refresh"))
    keyboard.adjust(1)
    await callback.message.edit_text(
        f"🛒 <b>{name}</b>\n\n💰 {item.price}₽ / {tp}🎫\n\nВыберите способ оплаты:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("shop_buy_rubles_"))
async def shop_buy_rubles_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("shop_buy_rubles_", "")
    if card_id not in shop_items:
        await callback.answer("❌ Товар уже куплен!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    item = shop_items[card_id]
    if datetime.fromisoformat(item.expires_at) <= datetime.now():
        del shop_items[card_id]; save_data()
        await callback.answer("❌ Срок товара истёк!", show_alert=True); return

    # Проверяем дубли заказов
    dup = [o for o in orders.values() if o.user_id == user.user_id and o.card_id == card_id and o.status == "pending"]
    if dup:
        await callback.answer("❌ У вас уже есть заказ на этот товар!", show_alert=True); return

    dp = get_price_with_discount(item.price, user.level)
    if card_id.startswith('skip_card_cooldown'):
        product_type, name, stars_price = "skip_card", "⚡ Скип кулдауна карточки", SKIP_CARD_COOLDOWN_STARS
    elif card_id.startswith('skip_trade_cooldown'):
        product_type, name, stars_price = "skip_trade", "🔄 Скип кулдауна обменов", SKIP_TRADE_COOLDOWN_STARS
    else:
        card = cards.get(card_id)
        if not card:
            await callback.answer("❌ Карточка не найдена!", show_alert=True); return
        product_type = "shop_card"
        name = f"{get_rarity_color(card.rarity)} {card.name}"
        stars_price = SHOP_PRICES_STARS.get(card.rarity, 10)

    order_id = f"order_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, card_id, dp)
    orders[order_id] = order
    if not card_id.startswith('skip_'):
        if card_id in shop_items:
            del shop_items[card_id]
    save_data()

    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 {name}\n💰 {dp}₽\n🆔 <code>{order_id}</code>\n\n"
        f"📝 Запомните номер заказа для отправки скриншота через /payment"
    )
    await show_payment_methods(callback, product_type, card_id, item.price, stars_price, name, user.level)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"🛒 Новый заказ!\n🆔 {order_id}\n👤 @{user.username}\n🎴 {name}\n💰 {dp}₽")
        except: pass
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("shop_buy_token_confirm_"))
async def shop_buy_token_confirm_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("shop_buy_token_confirm_", "")
    if card_id not in shop_items:
        await callback.answer("❌ Товар уже куплен!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    item = shop_items[card_id]
    tp = get_token_price(item.price)
    if user.tokens < tp:
        await callback.answer(f"❌ Нужно {tp}🎫, у вас {user.tokens}🎫", show_alert=True); return

    if card_id.startswith('skip_card_cooldown'):
        user.skip_card_cooldown_available = True; name = "⚡ Скип кулдауна карточки"
    elif card_id.startswith('skip_trade_cooldown'):
        user.skip_trade_cooldown_available = True; name = "🔄 Скип кулдауна обменов"
    else:
        card = cards.get(card_id)
        if not card:
            await callback.answer("❌ Карточка не найдена!", show_alert=True); return
        name = f"{get_rarity_color(card.rarity)} {card.name}"
        user.cards[card_id] = user.cards.get(card_id, 0) + 1
        user.opened_packs += 1

    user.tokens -= tp
    del shop_items[card_id]
    update_user_interaction(user)
    save_data()
    await callback.message.edit_text(
        f"✅ <b>Покупка за токены!</b>\n\n🎁 {name}\n💸 -{tp}🎫\n💰 Баланс: {user.tokens}🎫"
    )
    await callback.answer("✅ Куплено!")


# ══════════════════════════════════════════
# Подарок (покупка в подарок)
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data.startswith("shop_gift_"))
async def shop_gift_select_handler(callback: types.CallbackQuery, state: FSMContext):
    card_id = callback.data.replace("shop_gift_", "")
    if card_id not in shop_items:
        await callback.answer("❌ Товар уже куплен!", show_alert=True); return
    await state.update_data(gift_card_id=card_id)
    await callback.message.answer(
        "🎁 <b>Подарок</b>\n\nВведите @username получателя подарка:"
    )
    from states import ShopStates
    await state.set_state(ShopStates.entering_gift_username)
    await callback.answer()


@router.message(F.text)
async def shop_gift_username_handler(message: types.Message, state: FSMContext):
    from states import ShopStates
    current = await state.get_state()
    if current != ShopStates.entering_gift_username:
        return False  # не наше — пропускаем

    username = message.text.strip().lstrip('@')
    if username.lower() in ["/refresh", "отмена", "cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return

    recipient = None
    for u in users.values():
        if u.username.lower() == username.lower():
            recipient = u; break
    if not recipient:
        await message.answer(f"❌ @{username} не найден в системе. Попробуйте ещё:"); return

    data = await state.get_data()
    card_id = data.get('gift_card_id')
    if not card_id or card_id not in shop_items:
        await message.answer("❌ Товар больше не доступен."); await state.clear(); return

    item = shop_items[card_id]
    user = get_or_create_user(message.from_user.id)
    dp = get_price_with_discount(item.price, user.level)
    card = cards.get(card_id)
    name = f"{get_rarity_color(card.rarity)} {card.name}" if card else card_id

    order_id = f"gift_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, card_id, dp, gift_to_user_id=recipient.user_id)
    orders[order_id] = order
    if card_id in shop_items:
        del shop_items[card_id]
    save_data()

    await message.answer(
        f"✅ <b>Заказ-подарок создан!</b>\n\n"
        f"🎁 {name}\n👤 Получатель: @{recipient.username}\n"
        f"💰 {dp}₽\n🆔 <code>{order_id}</code>\n\n"
        f"Отправьте скриншот оплаты через /payment после оплаты."
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"🎁 Подарок!\n🆔 {order_id}\n👤 От: @{user.username} → @{recipient.username}\n🎴 {name}\n💰 {dp}₽")
        except: pass
    await state.clear()


# ══════════════════════════════════════════
# Лутбоксы
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "shop_lootboxes")
async def shop_lootboxes_handler(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    keyboard = InlineKeyboardBuilder()
    for key, info in LOOTBOX_PRICES.items():
        rub = info["rubles"]
        tok = info["tokens"]
        if rub > 0:
            label = f"{info['name']} — {rub}₽"
        else:
            label = f"{info['name']} — {tok}🎫"
        keyboard.add(InlineKeyboardButton(text=label, callback_data=f"lootbox_buy_{key}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад в магазин", callback_data="shop_refresh"))
    keyboard.adjust(1)
    await callback.message.edit_text(
        f"📦 <b>Лутбоксы</b>\n\n"
        f"💰 Ваши токены: {user.tokens}🎫\n\n"
        f"<b>Доступные паки:</b>\n"
        f"📦 Базовый пак — 3 карточки (1 базовая гарант.) — 79₽\n"
        f"💠 Крутой пак — 5 карточек (1 крутая гарант.) — 149₽\n"
        f"✨ Легендарный пак — 3 карточки (1 лег. гарант.) — 249₽\n"
        f"🎫 Токен-пак — 3 карточки (базовые) — 50🎫\n\n"
        f"<i>При любом паке есть шанс получить карточку выше гарантированной!</i>",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("lootbox_buy_"))
async def lootbox_buy_handler(callback: types.CallbackQuery):
    key = callback.data.replace("lootbox_buy_", "")
    info = LOOTBOX_PRICES.get(key)
    if not info:
        await callback.answer("❌ Пак не найден", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)

    # Токен-пак
    if info["tokens"] > 0:
        if user.tokens < info["tokens"]:
            await callback.answer(f"❌ Нужно {info['tokens']}🎫, у вас {user.tokens}🎫", show_alert=True); return
        user.tokens -= info["tokens"]
        results = _open_lootbox(info)
        for card_id, card in results:
            user.cards[card_id] = user.cards.get(card_id, 0) + 1
            user.opened_packs += 1
        update_user_interaction(user)
        save_data()
        cards_text = "\n".join([f"• {get_rarity_color(c.rarity)} {c.name}" for _, c in results])
        await callback.message.edit_text(
            f"📦 <b>{info['name']} открыт!</b>\n\n"
            f"💸 Потрачено: {info['tokens']}🎫\n\n"
            f"<b>Ваши карточки:</b>\n{cards_text}\n\n"
            f"Карточки добавлены в инвентарь!"
        )
    else:
        # Рублёвый пак — создаём заказ
        order_id = f"loot_{key}_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
        order = Order(order_id, user.user_id, f"lootbox_{key}", info["rubles"])
        orders[order_id] = order
        save_data()
        await callback.message.answer(
            f"✅ <b>Заказ на {info['name']} создан!</b>\n\n"
            f"💰 Сумма: {info['rubles']}₽\n🆔 <code>{order_id}</code>\n\n"
            f"Оплатите и отправьте скриншот через /payment"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                    f"📦 Лутбокс!\n🆔 {order_id}\n👤 @{user.username}\n🎴 {info['name']}\n💰 {info['rubles']}₽")
            except: pass
    await callback.answer()


def _open_lootbox(info: dict):
    """Открываем лутбокс и возвращаем список (card_id, card)."""
    guaranteed_rarity = info["guaranteed"]
    count = info["cards"]
    results = []

    guaranteed_cards = [cid for cid, c in cards.items() if c.rarity == guaranteed_rarity]
    if not guaranteed_cards:
        guaranteed_cards = list(cards.keys())

    if guaranteed_cards:
        gid = random.choice(guaranteed_cards)
        results.append((gid, cards[gid]))

    for _ in range(count - 1):
        # Случайные карточки с весами
        pool = []
        weights = {"basic": 70, "cool": 20, "legendary": 8, "vinyl figure": 2}
        for cid, c in cards.items():
            pool.extend([cid] * weights.get(c.rarity, 1))
        if pool:
            cid = random.choice(pool)
            results.append((cid, cards[cid]))

    return results


# ══════════════════════════════════════════
# Помощь по магазину
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "shop_help")
async def shop_help_handler(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    discount = get_level_discount(user.level)
    await callback.message.answer(
        f"🛒 <b>Как работает магазин</b>\n\n"
        f"• Новые карточки появляются каждые 12 часов\n"
        f"• Можно платить рублями или токенами 🎫\n"
        f"• Можно купить карточку <b>в подарок</b> другому игроку\n"
        f"• 📦 <b>Лутбоксы</b> — наборы карточек с гарантированной редкостью\n"
        f"• 🔥 <b>Флэш-скидки</b> — иногда цены временно снижаются\n"
        f"• Ваша скидка за уровень {user.level}: {discount}%\n\n"
        f"<b>Цены по редкостям:</b>\n"
        f"⚪ Обычная: {SHOP_PRICES['basic']}₽ / {get_token_price(SHOP_PRICES['basic'])}🎫\n"
        f"🔵 Крутая: {SHOP_PRICES['cool']}₽ / {get_token_price(SHOP_PRICES['cool'])}🎫\n"
        f"🟡 Легендарная: {SHOP_PRICES['legendary']}₽ / {get_token_price(SHOP_PRICES['legendary'])}🎫\n"
        f"🟣 Виниловая: {SHOP_PRICES['vinyl figure']}₽ / {get_token_price(SHOP_PRICES['vinyl figure'])}🎫"
    )
    await callback.answer()


# ══════════════════════════════════════════
# Эксклюзивы
# ══════════════════════════════════════════
@router.message(F.text == "🎪 Эксклюзивы")
async def exclusive_shop_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    # Подписка проверяется при /start
    user = get_or_create_user(message.from_user.id)
    discount = get_level_discount(user.level)
    active = [ec for ec in exclusive_cards.values() if ec.can_purchase()]
    if not active:
        await message.answer("🎪 <b>Эксклюзивы</b>\n\nСейчас нет доступных эксклюзивных карточек."); return
    keyboard = InlineKeyboardBuilder()
    for exc in active[:10]:
        card = cards.get(exc.card_id)
        if not card: continue
        remaining = exc.total_copies - exc.sold_copies
        dp = get_price_with_discount(exc.price, user.level)
        tp = get_token_price(exc.price)
        price_text = f"{dp}₽" if discount else f"{exc.price}₽"
        flash = ""
        if hasattr(exc, 'flash_sale_until') and exc.flash_sale_until:
            if datetime.fromisoformat(exc.flash_sale_until) > datetime.now():
                flash = "🔥 "
        keyboard.add(InlineKeyboardButton(
            text=f"{flash}{get_rarity_color(card.rarity)} {card.name} — {price_text}/{tp}🎫 ({remaining}/{exc.total_copies})",
            callback_data=f"buy_exclusive_tokens_{exc.card_id}"
        ))
    keyboard.adjust(1)
    disc_text = f"\n🎁 Ваша скидка: {discount}%" if discount else ""
    await message.answer(
        f"🎪 <b>ЭКСКЛЮЗИВНЫЕ КАРТОЧКИ</b>\n\n"
        f"🔥 Только здесь! Только ограниченным тиражом!{disc_text}\n\n"
        f"💰 Ваши токены: {user.tokens}🎫",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(lambda c: c.data.startswith("buy_exclusive_tokens_"))
async def buy_exclusive_select_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("buy_exclusive_tokens_", "")
    if card_id not in exclusive_cards:
        await callback.answer("❌ Карточка не найдена!", show_alert=True); return
    exc = exclusive_cards[card_id]
    card = cards.get(card_id)
    if not card or not exc.can_purchase():
        await callback.answer("❌ Карточка недоступна!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    dp = get_price_with_discount(exc.price, user.level)
    tp = get_token_price(exc.price)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f"💳 За рубли ({dp}₽)", callback_data=f"buy_exclusive_rubles_{card_id}"))
    keyboard.add(InlineKeyboardButton(text=f"🎫 За токены ({tp}🎫)", callback_data=f"buy_exclusive_token_confirm_{card_id}"))
    keyboard.add(InlineKeyboardButton(text="🎁 В подарок", callback_data=f"excl_gift_{card_id}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    keyboard.adjust(1)
    await callback.message.edit_text(
        f"🎪 {get_rarity_color(card.rarity)} <b>{card.name}</b>\n\n"
        f"💰 {exc.price}₽ / {tp}🎫\n"
        f"📦 Осталось: {exc.total_copies - exc.sold_copies}/{exc.total_copies}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("buy_exclusive_rubles_"))
async def buy_exclusive_rubles_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("buy_exclusive_rubles_", "")
    exc = exclusive_cards.get(card_id)
    card = cards.get(card_id)
    if not exc or not card or not exc.can_purchase():
        await callback.answer("❌ Карточка недоступна!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    dp = get_price_with_discount(exc.price, user.level)
    order_id = f"exclusive_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    order = Order(order_id, user.user_id, card_id, dp)
    orders[order_id] = order
    save_data()
    name = f"🎪 {get_rarity_color(card.rarity)} {card.name} (ЭКСКЛЮЗИВ)"
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n🎁 {name}\n💰 {dp}₽\n🆔 <code>{order_id}</code>\n\n"
        f"Оплатите и отправьте скриншот через /payment"
    )
    await show_payment_methods(callback, "exclusive_card", card_id, exc.price,
                               SHOP_PRICES_STARS.get(card.rarity, 25), name, user.level)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"🎪 Эксклюзив!\n🆔 {order_id}\n👤 @{user.username}\n🎴 {card.name}\n💰 {dp}₽")
        except: pass
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("buy_exclusive_token_confirm_"))
async def buy_exclusive_token_confirm_handler(callback: types.CallbackQuery):
    card_id = callback.data.replace("buy_exclusive_token_confirm_", "")
    exc = exclusive_cards.get(card_id)
    card = cards.get(card_id)
    if not exc or not card or not exc.can_purchase():
        await callback.answer("❌ Карточка недоступна!", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    tp = get_token_price(exc.price)
    if user.tokens < tp:
        await callback.answer(f"❌ Нужно {tp}🎫, у вас {user.tokens}🎫", show_alert=True); return
    user.tokens -= tp
    user.cards[card_id] = user.cards.get(card_id, 0) + 1
    user.opened_packs += 1
    exc.sold_copies += 1
    if exc.sold_copies >= exc.total_copies:
        exc.is_active = False
    update_user_interaction(user)
    save_data()
    await callback.message.edit_text(
        f"✅ <b>Куплено за токены!</b>\n\n"
        f"🎪 {get_rarity_color(card.rarity)} {card.name}\n"
        f"💸 -{tp}🎫\n💰 Баланс: {user.tokens}🎫\n\nКарточка в инвентаре!"
    )
    await callback.answer("✅ Куплено!")


@router.callback_query(lambda c: c.data.startswith("excl_gift_"))
async def excl_gift_handler(callback: types.CallbackQuery, state: FSMContext):
    card_id = callback.data.replace("excl_gift_", "")
    exc = exclusive_cards.get(card_id)
    if not exc or not exc.can_purchase():
        await callback.answer("❌ Карточка недоступна!", show_alert=True); return
    await state.update_data(gift_excl_id=card_id)
    from states import ShopStates
    await state.set_state(ShopStates.entering_gift_username)
    await callback.message.answer("🎁 Введите @username получателя подарка:")
    await callback.answer()
