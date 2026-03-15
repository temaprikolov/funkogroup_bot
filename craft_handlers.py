# craft_handlers.py — Прокачка и крафт карточек
import random
import logging
from typing import Optional

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import CRAFT_RECIPES

craft_router = Router()
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
users = None
cards = None
save_data = None
get_or_create_user = None
get_rarity_color = None
get_rarity_name = None
check_access_before_handle = None

RECIPE_NAMES = {
    "basic_to_cool":     "3 обычные → 1 крутая",
    "cool_to_legendary": "3 крутые → 1 легендарная (50%)",
    "cool_to_leg_sure":  "5 крутых + 50🎫 → 1 легендарная (100%)",
    "leg_to_vinyl":      "3 легендарные + 150🎫 → Виниловая (30%)",
}

RARITY_FROM = {
    "basic_to_cool":     "basic",
    "cool_to_legendary": "cool",
    "cool_to_leg_sure":  "cool",
    "leg_to_vinyl":      "legendary",
}


def setup_craft_handlers(bot_i, users_d, cards_d, save_fn, get_user_fn,
                         color_fn, name_fn, access_fn):
    global bot, users, cards, save_data, get_or_create_user
    global get_rarity_color, get_rarity_name, check_access_before_handle
    bot = bot_i
    users = users_d
    cards = cards_d
    save_data = save_fn
    get_or_create_user = get_user_fn
    get_rarity_color = color_fn
    get_rarity_name = name_fn
    check_access_before_handle = access_fn


# ══════════════════════════════════════════
# Меню прокачки
# ══════════════════════════════════════════
@craft_router.message(F.text == "⚗️ Прокачка")
async def craft_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    user = get_or_create_user(message.from_user.id)

    basic_count = sum(q for cid, q in user.cards.items()
                      if cards.get(cid) and cards[cid].rarity == "basic")
    cool_count = sum(q for cid, q in user.cards.items()
                     if cards.get(cid) and cards[cid].rarity == "cool")
    leg_count = sum(q for cid, q in user.cards.items()
                    if cards.get(cid) and cards[cid].rarity == "legendary")

    keyboard = InlineKeyboardBuilder()
    for recipe_key, recipe in CRAFT_RECIPES.items():
        from_rarity = recipe["from"]
        count_needed = recipe["count"]
        token_cost = recipe["token_cost"]
        success = recipe["success_rate"]

        # Подсчитываем доступные карты нужной редкости
        available = sum(q for cid, q in user.cards.items()
                        if cards.get(cid) and cards[cid].rarity == from_rarity)

        can_craft = available >= count_needed and user.tokens >= token_cost
        label = RECIPE_NAMES[recipe_key]
        status = "✅" if can_craft else "🔒"
        keyboard.add(InlineKeyboardButton(
            text=f"{status} {label}",
            callback_data=f"craft_{recipe_key}"
        ))

    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    keyboard.adjust(1)

    await message.answer(
        f"⚗️ <b>Прокачка карточек</b>\n\n"
        f"📦 У вас:\n"
        f"• ⚪ Обычных: {basic_count}\n"
        f"• 🔵 Крутых: {cool_count}\n"
        f"• 🟡 Легендарных: {leg_count}\n"
        f"• 🎫 Токенов: {user.tokens}\n\n"
        f"<b>Рецепты:</b>\n"
        f"• 3 обычные → 1 крутая (100%)\n"
        f"• 3 крутые → 1 легендарная (50%)\n"
        f"• 5 крутых + 50🎫 → 1 легендарная (100%)\n"
        f"• 3 легендарные + 150🎫 → Виниловая (30%)\n\n"
        f"<i>✅ — доступно для крафта, 🔒 — нужно больше карт/токенов</i>",
        reply_markup=keyboard.as_markup()
    )


@craft_router.callback_query(lambda c: c.data.startswith("craft_"))
async def craft_recipe_handler(callback: types.CallbackQuery):
    recipe_key = callback.data.replace("craft_", "")
    recipe = CRAFT_RECIPES.get(recipe_key)
    if not recipe:
        await callback.answer("❌ Рецепт не найден", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id)
    from_rarity = recipe["from"]
    count_needed = recipe["count"]
    token_cost = recipe["token_cost"]
    success_rate = recipe["success_rate"]
    to_rarity = recipe["to"]

    # Проверка наличия карт нужной редкости
    available_cards = [(cid, q) for cid, q in user.cards.items()
                       if cards.get(cid) and cards[cid].rarity == from_rarity]
    available_count = sum(q for _, q in available_cards)

    if available_count < count_needed:
        await callback.answer(
            f"❌ Нужно {count_needed} карт редкости «{get_rarity_name(from_rarity)}», "
            f"у вас {available_count}",
            show_alert=True
        )
        return
    if user.tokens < token_cost:
        await callback.answer(
            f"❌ Нужно {token_cost}🎫 токенов, у вас {user.tokens}",
            show_alert=True
        )
        return

    # Показываем предпросмотр с подтверждением
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="⚗️ Крафтить!",
        callback_data=f"craft_confirm_{recipe_key}"
    ))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="craft_back"))
    keyboard.adjust(1)

    rarity_from_icon = get_rarity_color(from_rarity)
    rarity_to_icon = get_rarity_color(to_rarity)

    token_line = f"\n💸 Стоимость: {token_cost}🎫" if token_cost > 0 else ""
    await callback.message.edit_text(
        f"⚗️ <b>Крафт: {RECIPE_NAMES[recipe_key]}</b>\n\n"
        f"Вы потратите: {count_needed}x {rarity_from_icon} {get_rarity_name(from_rarity)}{token_line}\n"
        f"Вы получите: 1x {rarity_to_icon} {get_rarity_name(to_rarity)}\n"
        f"Шанс успеха: <b>{success_rate}%</b>\n\n"
        f"<i>При неудаче карты и токены НЕ возвращаются.</i>\n\n"
        f"Подтвердить крафт?",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@craft_router.callback_query(lambda c: c.data == "craft_back")
async def craft_back_handler(callback: types.CallbackQuery):
    await callback.message.delete()
    await craft_menu(callback.message)
    await callback.answer()


@craft_router.callback_query(lambda c: c.data.startswith("craft_confirm_"))
async def craft_confirm_handler(callback: types.CallbackQuery):
    recipe_key = callback.data.replace("craft_confirm_", "")
    recipe = CRAFT_RECIPES.get(recipe_key)
    if not recipe:
        await callback.answer("❌ Рецепт не найден", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id)
    from_rarity = recipe["from"]
    count_needed = recipe["count"]
    token_cost = recipe["token_cost"]
    success_rate = recipe["success_rate"]
    to_rarity = recipe["to"]

    # Повторная проверка
    available_cards = [(cid, q) for cid, q in user.cards.items()
                       if cards.get(cid) and cards[cid].rarity == from_rarity]
    available_count = sum(q for _, q in available_cards)

    if available_count < count_needed or user.tokens < token_cost:
        await callback.answer("❌ Недостаточно ресурсов!", show_alert=True)
        return

    # Списываем карты (берём с наименьшим количеством первыми — чтобы не оставлять дубли)
    available_cards.sort(key=lambda x: x[1])
    remaining_to_remove = count_needed
    for cid, qty in available_cards:
        if remaining_to_remove <= 0:
            break
        remove = min(qty, remaining_to_remove)
        user.cards[cid] = user.cards.get(cid, 0) - remove
        if user.cards[cid] <= 0:
            del user.cards[cid]
        remaining_to_remove -= remove

    # Списываем токены
    user.tokens -= token_cost

    # Определяем успех
    success = random.randint(1, 100) <= success_rate

    if success:
        # Выбираем случайную карту нужной редкости
        target_cards = [cid for cid, c in cards.items() if c.rarity == to_rarity]
        if not target_cards:
            await callback.message.edit_text(
                f"❌ <b>Нет карточек редкости «{get_rarity_name(to_rarity)}» в системе.</b>\n"
                f"Ресурсы потрачены. Обратитесь к администратору."
            )
            save_data()
            await callback.answer()
            return
        new_card_id = random.choice(target_cards)
        new_card = cards[new_card_id]
        user.cards[new_card_id] = user.cards.get(new_card_id, 0) + 1
        save_data()
        rarity_icon = get_rarity_color(to_rarity)
        await callback.message.edit_text(
            f"⚗️ <b>Крафт успешен!</b> ✨\n\n"
            f"Вы получили: {rarity_icon} <b>{new_card.name}</b>\n"
            f"Редкость: {get_rarity_name(to_rarity)}\n\n"
            f"<i>Карточка добавлена в ваш инвентарь!</i>"
        )
    else:
        save_data()
        await callback.message.edit_text(
            f"⚗️ <b>Крафт провалился...</b> 💨\n\n"
            f"Шанс успеха был {success_rate}%, но удача отвернулась.\n"
            f"Ресурсы потрачены.\n\n"
            f"<i>Попробуйте ещё раз!</i>"
        )

    await callback.answer()
