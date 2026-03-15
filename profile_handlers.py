# profile_handlers.py — Профиль, уведомления, поддержка/премиум
import random
import logging
from datetime import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import *

profile_router = Router()
router = profile_router  # CRITICAL FIX
logger = logging.getLogger(__name__)

# Глобальные переменные (устанавливаются через setup_profile_handlers)
bot = None
users = None
cards = None
orders = None
save_data = None
get_or_create_user = None
check_access_before_handle = None
check_subscription = None
get_level_discount = None
get_price_with_discount = None
get_token_price = None
get_rarity_color = None
get_rarity_name = None
can_open_card = None
can_trade = None
get_card_cooldown_hours = None
get_trade_cooldown_hours = None
get_cooldown_by_level = None
get_level_progress_bar = None
calculate_level_exp = None
get_personal_recommendations = None
get_main_menu = None
show_payment_methods = None

def setup_profile_handlers(bot_i, users_d, cards_d, orders_d, save_fn,
                            get_user_fn, access_fn, sub_fn,
                            level_disc_fn, price_disc_fn, token_price_fn,
                            rarity_color_fn, rarity_name_fn,
                            can_open_fn, can_trade_fn,
                            card_cd_fn, trade_cd_fn, cd_by_level_fn,
                            progress_fn, calc_exp_fn, rec_fn, main_menu_fn,
                            payment_methods_fn):
    global bot, users, cards, orders, save_data
    global get_or_create_user, check_access_before_handle, check_subscription
    global get_level_discount, get_price_with_discount, get_token_price
    global get_rarity_color, get_rarity_name
    global can_open_card, can_trade, get_card_cooldown_hours, get_trade_cooldown_hours
    global get_cooldown_by_level, get_level_progress_bar, calculate_level_exp
    global get_personal_recommendations, get_main_menu, show_payment_methods
    bot = bot_i; users = users_d; cards = cards_d; orders = orders_d; save_data = save_fn
    get_or_create_user = get_user_fn; check_access_before_handle = access_fn
    check_subscription = sub_fn; get_level_discount = level_disc_fn
    get_price_with_discount = price_disc_fn; get_token_price = token_price_fn
    get_rarity_color = rarity_color_fn; get_rarity_name = rarity_name_fn
    can_open_card = can_open_fn; can_trade = can_trade_fn
    get_card_cooldown_hours = card_cd_fn; get_trade_cooldown_hours = trade_cd_fn
    get_cooldown_by_level = cd_by_level_fn; get_level_progress_bar = progress_fn
    calculate_level_exp = calc_exp_fn; get_personal_recommendations = rec_fn
    get_main_menu = main_menu_fn; show_payment_methods = payment_methods_fn

@router.message(lambda message: message.text == "👤 Профиль")
async def profile_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    # Подписка проверяется при /start
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
    discount = get_level_discount(user.level)
    response = (
        f"👤 <b>Профиль {message.from_user.first_name}</b>\n\n"
        f"📊 <b>Основная статистика:</b>\n"
        f"🎴 Открыто карточек: {user.opened_packs}\n"
        f"📚 Всего карточек: {sum(user.cards.values())}\n"
        f"⭐ Уникальных карточек: {len(user.cards)}\n"
        f"📈 Процент коллекции: {total_percentage:.1f}%\n"
        f"🎫 Токенов: <b>{user.tokens}</b>\n\n"
        f"⏰ <b>Кулдаун карточек ({card_cooldown_hours}ч):</b> {card_cooldown_status}\n"
        f"🔄 <b>Кулдаун обменов ({trade_cooldown_hours}ч):</b> {trade_cooldown_status}\n\n"
        f"🎁 <b>Скидка в магазине:</b> {discount}%\n"
    )
    if user.skip_card_cooldown_available:
        response += f"⚡ <b>Есть скип кулдауна карточки!</b> (одноразовый)\n"
    if user.skip_trade_cooldown_available:
        response += f"🔄 <b>Есть скип кулдауна обменов!</b> (одноразовый)\n"
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
    response += f"\n🎮 <b>Игровая статистика:</b>\n"
    response += f"📊 Общий винрейт: {user.game_stats.winrate():.1f}%\n"
    response += f"🗿 КНБ: {user.game_stats.rock_paper_scissors['wins']}П / {user.game_stats.rock_paper_scissors['losses']}Пр / {user.game_stats.rock_paper_scissors['draws']}Н\n"
    response += f"🎲 Дайс: {user.game_stats.dice['wins']}П / {user.game_stats.dice['losses']}Пр / {user.game_stats.dice['draws']}Н\n"
    response += f"🎰 Автоматы: {user.game_stats.slots['wins']}П / {user.game_stats.slots['losses']}Пр / {user.game_stats.slots['draws']}Н\n"
    recommendations = get_personal_recommendations(message.from_user.id, 2)
    if recommendations:
        response += "\n🎯 <b>Вам может понравиться:</b>\n"
        for rec in recommendations:
            card = rec['card']
            rarity_icon = get_rarity_color(card.rarity)
            discounted = get_price_with_discount(rec['price'], user.level)
            price_text = f"{discounted}₽" if discount > 0 else f"{rec['price']}₽"
            response += f"{rarity_icon} {card.name} - {price_text}\n"
        response += "<i>На основе ваших предпочтений</i>\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="🔔 Настройки уведомлений",
        callback_data="notification_settings"
    ))
    await message.answer(response, reply_markup=keyboard.as_markup())

@router.callback_query(lambda c: c.data == "notification_settings")
async def notification_settings_handler(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    status_shop = "✅ Вкл" if user.notification_settings.shop_updates else "❌ Выкл"
    status_card = "✅ Вкл" if user.notification_settings.card_available else "❌ Выкл"
    status_promo = "✅ Вкл" if user.notification_settings.promo_offers else "❌ Выкл"
    status_trade = "✅ Вкл" if user.notification_settings.trade_offers else "❌ Выкл"
    status_system = "✅ Вкл" if user.notification_settings.system_messages else "❌ Выкл"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text=f"🛒 Магазин: {status_shop}",
        callback_data="toggle_notif_shop"
    ))
    keyboard.add(InlineKeyboardButton(
        text=f"🎴 Доступность карточки: {status_card}",
        callback_data="toggle_notif_card"
    ))
    keyboard.add(InlineKeyboardButton(
        text=f"🎁 Промо: {status_promo}",
        callback_data="toggle_notif_promo"
    ))
    keyboard.add(InlineKeyboardButton(
        text=f"🔄 Обмены: {status_trade}",
        callback_data="toggle_notif_trade"
    ))
    keyboard.add(InlineKeyboardButton(
        text=f"⚙️ Системные: {status_system}",
        callback_data="toggle_notif_system"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔙 Назад в профиль",
        callback_data="back_to_profile"
    ))
    keyboard.adjust(1)
    await callback.message.edit_text(
        "🔔 <b>Настройки уведомлений</b>\n\n"
        "Вы можете включить или отключить следующие уведомления:\n\n"
        "• <b>Магазин</b> - уведомления о новых карточках в магазине\n"
        "• <b>Доступность карточки</b> - когда можно открыть новую карточку\n"
        "• <b>Промо</b> - персональные предложения и скидки\n"
        "• <b>Обмены</b> - уведомления о предложениях обмена\n"
        "• <b>Системные</b> - важные системные уведомления\n\n"
        "<i>Рассылки (административные) отключить нельзя</i>",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "toggle_notif_shop")
async def toggle_notif_shop(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    user.notification_settings.shop_updates = not user.notification_settings.shop_updates
    save_data()
    await notification_settings_handler(callback)

@router.callback_query(lambda c: c.data == "toggle_notif_card")
async def toggle_notif_card(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    user.notification_settings.card_available = not user.notification_settings.card_available
    save_data()
    await notification_settings_handler(callback)

@router.callback_query(lambda c: c.data == "toggle_notif_promo")
async def toggle_notif_promo(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    user.notification_settings.promo_offers = not user.notification_settings.promo_offers
    save_data()
    await notification_settings_handler(callback)

@router.callback_query(lambda c: c.data == "toggle_notif_trade")
async def toggle_notif_trade(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    user.notification_settings.trade_offers = not user.notification_settings.trade_offers
    save_data()
    await notification_settings_handler(callback)

@router.callback_query(lambda c: c.data == "toggle_notif_system")
async def toggle_notif_system(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    user.notification_settings.system_messages = not user.notification_settings.system_messages
    save_data()
    await notification_settings_handler(callback)

@router.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile_handler(callback: types.CallbackQuery):
    await profile_menu(callback.message)
    await callback.answer()

@router.message(F.text == "💝 Поддержать проект")
async def support_menu(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id):
        return
    # Подписка проверяется при /start
    user = get_or_create_user(message.from_user.id)
    discount = get_level_discount(user.level)
    premium_discounted = get_price_with_discount(PREMIUM_COST, user.level)
    cd_discounted = get_price_with_discount(REDUCED_CD_COST, user.level)
    trade_cd_discounted = get_price_with_discount(REDUCED_TRADE_CD_COST, user.level)
    level1_discounted = get_price_with_discount(BUY_LEVEL_1_COST, user.level)
    level5_discounted = get_price_with_discount(BUY_LEVEL_5_COST, user.level)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="💎 Премиум",
        callback_data="buy_premium"
    ))
    keyboard.add(InlineKeyboardButton(
        text="⚡ Уменьшить кулдаун карточек",
        callback_data="buy_reduced_cd"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🔄 Уменьшить кулдаун обменов",
        callback_data="buy_reduced_trade_cd"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🎮 Купить 1 уровень",
        callback_data="buy_level_1"
    ))
    keyboard.add(InlineKeyboardButton(
        text="🎮🎮 Купить 5 уровней",
        callback_data="buy_level_5"
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
    discount_text = f"\n🎁 <b>Ваша скидка {discount}%:</b>" if discount > 0 else ""
    await message.answer(
        f"💝 <b>Поддержать проект</b>\n\n"
        f"Вы можете поддержать развитие бота:\n\n"
        f"💰 <b>Разовое пожертвование:</b>\n"
        f"Любая сумма на развитие проекта\n\n"
        f"💎 <b>Премиум подписка:</b>\n"
        f"Исходная цена: {PREMIUM_COST}₽/месяц{discount_text}\n"
        f"<b>Ваша цена:</b> {premium_discounted}₽/месяц\n"
        f"• Удвоенный шанс на редкие карты\n"
        f"• 10 карточек при подключении\n"
        f"• Ежедневный бонус: 3 карточки\n"
        f"• 3 токена за карточку вместо 1!\n\n"
        f"⚡ <b>Снизить кулдаун карточек:</b>\n"
        f"Исходная цена: {REDUCED_CD_COST}₽/месяц{discount_text}\n"
        f"<b>Ваша цена:</b> {cd_discounted}₽/месяц\n"
        f"• Кулдаун сократится с 4х часов до 2х!\n\n"
        f"🔄 <b>Снизить кулдаун обменов:</b>\n"
        f"Исходная цена: {REDUCED_TRADE_CD_COST}₽/месяц{discount_text}\n"
        f"<b>Ваша цена:</b> {trade_cd_discounted}₽/месяц\n"
        f"• Кулдаун обменов сократится с 4х часов до 2х!\n\n"
        f"🎮 <b>Купить уровни:</b>\n"
        f"• 1 уровень: {level1_discounted}₽ (было {BUY_LEVEL_1_COST}₽)\n"
        f"• 5 уровней: {level5_discounted}₽ (было {BUY_LEVEL_5_COST}₽) - выгоднее!\n\n"
        f"После оплаты отправьте скриншот: @prikolovwork",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(lambda c: c.data == "buy_premium")
async def buy_premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    await show_payment_methods(
        callback=callback,
        product_type="premium",
        product_id="premium_30_days",
        price=PREMIUM_COST,
        stars_price=PREMIUM_STARS,
        description="Премиум подписка на 1 месяц",
        level=user.level
    )

@router.callback_query(lambda c: c.data == "buy_reduced_cd")
async def buy_reduced_cd_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    discounted_price = get_price_with_discount(REDUCED_CD_COST, user.level)
    order_id = f"reduced_cd_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    order = Order(order_id, user.user_id, "reduced_cd_30_days", discounted_price)
    orders[order_id] = order
    save_data()
    discount_text = f" (скидка {get_level_discount(user.level)}%)" if get_level_discount(user.level) > 0 else ""
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Уменьшенный кулдаун карточек на 1 месяц\n"
        f"💰 <b>Исходная сумма:</b> {REDUCED_CD_COST}₽{discount_text}\n"
        f"💳 <b>Итого к оплате:</b> {discounted_price}₽\n"
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
        stars_price=REDUCED_CD_STARS,
        description="Уменьшенный кулдаун карточек на 1 месяц",
        level=user.level
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"⚡ <b>Новый заказ на уменьшенный кулдаун!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Уменьшенный кулдаун карточек на 30 дней\n"
                     f"💰 <b>Сумма:</b> {discounted_price}₽ (исходная: {REDUCED_CD_COST}₽, скидка {get_level_discount(user.level)}%)\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@router.callback_query(lambda c: c.data == "buy_reduced_trade_cd")
async def buy_reduced_trade_cd_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    discounted_price = get_price_with_discount(REDUCED_TRADE_CD_COST, user.level)
    order_id = f"reduced_trade_cd_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    order = Order(order_id, user.user_id, "reduced_trade_cd_30_days", discounted_price)
    orders[order_id] = order
    save_data()
    discount_text = f" (скидка {get_level_discount(user.level)}%)" if get_level_discount(user.level) > 0 else ""
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Уменьшенный кулдаун обменов на 1 месяц\n"
        f"💰 <b>Исходная сумма:</b> {REDUCED_TRADE_CD_COST}₽{discount_text}\n"
        f"💳 <b>Итого к оплате:</b> {discounted_price}₽\n"
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
        stars_price=REDUCED_TRADE_CD_STARS,
        description="Уменьшенный кулдаун обменов на 1 месяц",
        level=user.level
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🔄 <b>Новый заказ на уменьшенный кулдаун обменов!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Уменьшенный кулдаун обменов на 30 дней\n"
                     f"💰 <b>Сумма:</b> {discounted_price}₽ (исходная: {REDUCED_TRADE_CD_COST}₽, скидка {get_level_discount(user.level)}%)\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@router.callback_query(lambda c: c.data == "buy_level_1")
async def buy_level_1_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    discounted_price = get_price_with_discount(BUY_LEVEL_1_COST, user.level)
    order_id = f"level1_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    order = Order(order_id, user.user_id, "buy_level_1", discounted_price)
    orders[order_id] = order
    save_data()
    discount_text = f" (скидка {get_level_discount(user.level)}%)" if get_level_discount(user.level) > 0 else ""
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Покупка 1 уровня\n"
        f"💰 <b>Исходная сумма:</b> {BUY_LEVEL_1_COST}₽{discount_text}\n"
        f"💳 <b>Итого к оплате:</b> {discounted_price}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )

    await show_payment_methods(
        callback=callback,
        product_type="level",
        product_id="buy_level_1",
        price=BUY_LEVEL_1_COST,
        stars_price=BUY_LEVEL_1_STARS,
        description="Покупка 1 уровня",
        level=user.level
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🎮 <b>Новый заказ на покупку уровня!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Покупка 1 уровня\n"
                     f"💰 <b>Сумма:</b> {discounted_price}₽ (исходная: {BUY_LEVEL_1_COST}₽, скидка {get_level_discount(user.level)}%)\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@router.callback_query(lambda c: c.data == "buy_level_5")
async def buy_level_5_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    discounted_price = get_price_with_discount(BUY_LEVEL_5_COST, user.level)
    order_id = f"level5_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
    order = Order(order_id, user.user_id, "buy_level_5", discounted_price)
    orders[order_id] = order
    save_data()
    discount_text = f" (скидка {get_level_discount(user.level)}%)" if get_level_discount(user.level) > 0 else ""
    await callback.message.answer(
        f"✅ <b>Заказ создан!</b>\n\n"
        f"🎁 <b>Товар:</b> Покупка 5 уровней\n"
        f"💰 <b>Исходная сумма:</b> {BUY_LEVEL_5_COST}₽{discount_text}\n"
        f"💳 <b>Итого к оплате:</b> {discounted_price}₽\n"
        f"🆔 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
        f"📝 <b>Запомните номер заказа!</b>\n"
        f"Он понадобится для отправки скриншота оплаты.\n\n"
        f"💵 <b>Далее:</b> выберите способ оплаты:"
    )
    await show_payment_methods(
        callback=callback,
        product_type="level",
        product_id="buy_level_5",
        price=BUY_LEVEL_5_COST,
        stars_price=BUY_LEVEL_5_STARS,
        description="Покупка 5 уровней",
        level=user.level
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🎮 <b>Новый заказ на покупку 5 уровней!</b>\n\n"
                     f"🆔 <b>Номер:</b> {order_id}\n"
                     f"👤 <b>Пользователь:</b> @{user.username or 'без username'}\n"
                     f"🎴 <b>Товар:</b> Покупка 5 уровней\n"
                     f"💰 <b>Сумма:</b> {discounted_price}₽ (исходная: {BUY_LEVEL_5_COST}₽, скидка {get_level_discount(user.level)}%)\n"
                     f"📅 <b>Создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Ожидайте скриншот оплаты от пользователя</i>"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@router.callback_query(lambda c: c.data.startswith("payment_method:"))
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
        "exclusive_card": "Эксклюзивная карточка",
        "skip_card": "⚡ Скип кулдауна карточки",
        "skip_trade": "🔄 Скип кулдауна обменов",
        "level": "🎮 Покупка уровня"
    }
    if product_id == "skip_card_cooldown":
        product_name = "⚡ Скип кулдауна карточки (одноразовый)"
    elif product_id == "skip_trade_cooldown":
        product_name = "🔄 Скип кулдауна обменов (одноразовый)"
    elif product_id == "buy_level_1":
        product_name = "🎮 Покупка 1 уровня"
    elif product_id == "buy_level_5":
        product_name = "🎮 Покупка 5 уровней"
    elif product_type in ["shop_card", "exclusive_card"]:
        card = cards.get(product_id)
        if card:
            rarity_icon = get_rarity_color(card.rarity)
            product_name = f"{rarity_icon} {card.name} ({get_rarity_name(card.rarity)})"
        else:
            product_name = product_names.get(product_type, "Товар")
    else:
        product_name = product_names.get(product_type, "Товар")
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
            f"📸 <b>После оплаты:</b>\n"
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

    elif method == "stars":
        # Создаём инвойс для оплаты звёздами
        from aiogram.types import LabeledPrice
        prices = [LabeledPrice(label=product_name, amount=price)]
        payload = f"{product_type}:{product_id}:{user.user_id}:{int(datetime.now().timestamp())}"
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=product_name,
            description=f"Оплата {product_name}",
            payload=payload,
            provider_token="",  # для звёзд оставляем пустым
            currency="XTR",
            prices=prices,
            start_parameter="stars_payment"
        )  

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    user = get_or_create_user(callback.from_user.id)
    await callback.message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_menu(user)
    )

