# inventory_addons.py — Вишлист и продажа дубликатов
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)
inventory_router = Router()

# ─── Ставки конвертации дубликатов в токены ──────────────────────────────────
DUPLICATE_TOKEN_RATES = {
    "basic":       1,
    "cool":        3,
    "legendary":  10,
    "vinyl figure": 30,
}
# Продаём копии сверх этого количества
DUPLICATE_KEEP_MIN = 1

# ─── Глобальные переменные ───────────────────────────────────────────────────
bot = None
users = None
cards = None
save_data = None
get_or_create_user = None
get_rarity_color = None
get_rarity_name = None
check_access_before_handle = None
check_and_award_achievements = None


def setup_inventory_addons(bot_i, users_d, cards_d, save_fn,
                           get_user_fn, rarity_color_fn, rarity_name_fn,
                           access_fn, achievements_fn=None):
    global bot, users, cards, save_data
    global get_or_create_user, get_rarity_color, get_rarity_name
    global check_access_before_handle, check_and_award_achievements
    bot = bot_i; users = users_d; cards = cards_d; save_data = save_fn
    get_or_create_user = get_user_fn
    get_rarity_color = rarity_color_fn
    get_rarity_name = rarity_name_fn
    check_access_before_handle = access_fn
    check_and_award_achievements = achievements_fn


# ════════════════════════════════════════════════════════════════════════════════
# ВИШЛИСТ
# ════════════════════════════════════════════════════════════════════════════════

@inventory_router.callback_query(lambda c: c.data.startswith("wishlist_add_"))
async def wishlist_add(callback: types.CallbackQuery):
    cid  = callback.data.replace("wishlist_add_", "")
    user = get_or_create_user(callback.from_user.id)
    card = cards.get(cid)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return

    wishlist = getattr(user, 'wishlist', [])
    if cid in wishlist:
        await callback.answer("💝 Уже в вишлисте!", show_alert=True)
        return

    wishlist.append(cid)
    user.wishlist = wishlist
    save_data()

    await callback.answer(f"💝 {card.name} добавлена в вишлист!", show_alert=True)


@inventory_router.callback_query(lambda c: c.data.startswith("wishlist_remove_"))
async def wishlist_remove(callback: types.CallbackQuery):
    cid  = callback.data.replace("wishlist_remove_", "")
    user = get_or_create_user(callback.from_user.id)
    card = cards.get(cid)

    wishlist = getattr(user, 'wishlist', [])
    if cid in wishlist:
        wishlist.remove(cid)
        user.wishlist = wishlist
        save_data()

    name = card.name if card else cid
    await callback.answer(f"💔 {name} убрана из вишлиста", show_alert=True)


@inventory_router.callback_query(lambda c: c.data == "my_wishlist")
async def my_wishlist(callback: types.CallbackQuery):
    user     = get_or_create_user(callback.from_user.id)
    wishlist = getattr(user, 'wishlist', [])

    if not wishlist:
        await callback.answer("💭 Вишлист пуст! Добавляйте карточки через инвентарь.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = ["💝 <b>Мой вишлист</b>\n"]
    for cid in wishlist:
        card = cards.get(cid)
        if not card:
            continue
        icon  = get_rarity_color(card.rarity)
        in_inv = cid in user.cards
        status = "✅ (есть)" if in_inv else "❌ (нет)"
        lines.append(f"{icon} {card.name} — {get_rarity_name(card.rarity)} {status}")
        kb.add(InlineKeyboardButton(
            text=f"💔 Убрать {card.name}",
            callback_data=f"wishlist_remove_{cid}"
        ))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(1)

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await callback.answer()


def build_card_view_keyboard(cid: str, user) -> types.InlineKeyboardMarkup:
    """
    Клавиатура при просмотре карточки в инвентаре.
    Включает кнопку вишлиста. Использовать вместо оригинальной в view_card_handler.
    """
    wishlist = getattr(user, 'wishlist', [])
    kb = InlineKeyboardBuilder()
    if cid in wishlist:
        kb.add(InlineKeyboardButton(text="💔 Убрать из вишлиста", callback_data=f"wishlist_remove_{cid}"))
    else:
        kb.add(InlineKeyboardButton(text="💝 В вишлист",          callback_data=f"wishlist_add_{cid}"))
    kb.add(InlineKeyboardButton(text="🔙 К инвентарю", callback_data="back_to_menu"))
    kb.adjust(1)
    return kb.as_markup()


async def notify_wishlist_match(users_dict: dict, bot_instance, new_card_ids: list, cards_dict: dict):
    """
    Вызывать из notify_shop_update() когда в магазин пришли новые карточки.
    Рассылает личные уведомления тем, у кого эта карта в вишлисте.
    """
    if not new_card_ids:
        return
    for user in users_dict.values():
        if user.is_banned or user.is_frozen:
            continue
        wishlist = getattr(user, 'wishlist', [])
        matches  = [cid for cid in new_card_ids if cid in wishlist]
        if not matches:
            continue
        try:
            lines = ["💝 <b>Карточки из вашего вишлиста появились в магазине!</b>\n"]
            for cid in matches:
                card = cards_dict.get(cid)
                if card:
                    icon = "⚪️" if card.rarity == "basic" else "🔵" if card.rarity == "cool" \
                        else "🟡" if card.rarity == "legendary" else "🟣"
                    lines.append(f"{icon} {card.name}")
            lines.append("\nОткройте 🛒 Магазин, пока карточка доступна!")
            await bot_instance.send_message(user.user_id, "\n".join(lines))
            import asyncio
            await asyncio.sleep(0.05)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════════
# ПРОДАЖА ДУБЛИКАТОВ
# ════════════════════════════════════════════════════════════════════════════════

@inventory_router.callback_query(lambda c: c.data == "sell_duplicates_menu")
async def sell_duplicates_menu(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)

    # Ищем карты с 2+ копиями — продаём всё кроме DUPLICATE_KEEP_MIN
    dupes = []
    total_tokens = 0
    for cid, qty in user.cards.items():
        sell_qty = qty - DUPLICATE_KEEP_MIN
        if sell_qty <= 0:
            continue
        card = cards.get(cid)
        if not card:
            continue
        rate   = DUPLICATE_TOKEN_RATES.get(card.rarity, 1)
        tokens = sell_qty * rate
        total_tokens += tokens
        dupes.append((cid, card, sell_qty, rate, tokens))

    if not dupes:
        await callback.answer(
            "♻️ Нет дубликатов для продажи!\n(Нужно 2+ копии одной карточки)",
            show_alert=True
        )
        return

    # Сортировка: сначала редкие
    rarity_order = {"vinyl figure": 0, "legendary": 1, "cool": 2, "basic": 3}
    dupes.sort(key=lambda x: rarity_order.get(x[1].rarity, 9))

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(
        text=f"♻️ Продать ВСЕ дубликаты (+{total_tokens}🎫)",
        callback_data="sell_duplicates_confirm_all"
    ))
    kb.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_menu"))
    kb.adjust(1)

    lines = ["♻️ <b>Продажа дубликатов</b>\n"]
    for cid, card, sell_qty, rate, tokens in dupes[:15]:
        icon = get_rarity_color(card.rarity)
        lines.append(f"{icon} {card.name}: ×{sell_qty} → +{tokens}🎫 ({rate}🎫/шт.)")
    if len(dupes) > 15:
        lines.append(f"<i>... и ещё {len(dupes)-15} позиций</i>")
    lines.append(f"\n<b>Итого: +{total_tokens}🎫</b>")
    lines.append(f"<i>Оставляем по {DUPLICATE_KEEP_MIN} копии каждой карточки</i>")

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await callback.answer()


@inventory_router.callback_query(lambda c: c.data == "sell_duplicates_confirm_all")
async def sell_duplicates_confirm_all(callback: types.CallbackQuery):
    user  = get_or_create_user(callback.from_user.id)
    total = 0
    sold  = 0

    for cid in list(user.cards.keys()):
        qty      = user.cards.get(cid, 0)
        sell_qty = qty - DUPLICATE_KEEP_MIN
        if sell_qty <= 0:
            continue
        card = cards.get(cid)
        if not card:
            continue
        rate  = DUPLICATE_TOKEN_RATES.get(card.rarity, 1)
        total += sell_qty * rate
        sold  += sell_qty
        user.cards[cid] = qty - sell_qty
        if user.cards[cid] <= 0:
            del user.cards[cid]

    if sold == 0:
        await callback.answer("Нет дубликатов", show_alert=True)
        return

    user.tokens = getattr(user, 'tokens', 0) + total
    # BUG FIX: market_sold_count tracks market listings, not duplicate-to-token conversions.
    # Don't inflate this counter here.
    save_data()

    await callback.message.edit_text(
        f"✅ <b>Дубликаты проданы!</b>\n\n"
        f"♻️ Карточек продано: {sold} шт.\n"
        f"💰 Получено: +{total}🎫\n"
        f"💰 Баланс: {user.tokens}🎫"
    )
    await callback.answer()
