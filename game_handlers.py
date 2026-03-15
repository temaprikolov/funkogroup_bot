# game_handlers.py — Игры
import asyncio
import random
import logging
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from games import determine_rps_winner, GameChallenge
from states import GameStates

game_router = Router()
logger = logging.getLogger(__name__)

# ─── Глобальные переменные (инициализируются из main.py) ───
bot = None
users = None
cards = None
active_game_challenges = None
save_data = None
get_or_create_user = None
get_user_by_username = None
is_video_card = None
get_rarity_color = None
get_rarity_name = None
main_logger = None
add_event_score = None   # функция для записи очков в текущий ивент

game_names = {
    "rps":   "🗿 Камень Ножницы Бумага",
    "dice":  "🎲 Дайс",
    "slots": "🎰 Автоматы",
}

RPS_ICONS = {"rock": "🗿 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}


def setup_game_handlers(bot_instance, users_dict, cards_dict, challenges_dict, save_func,
                        get_user_func, get_by_username_func, is_video_func, get_color_func,
                        get_name_func, logger_instance, add_event_score_func=None):
    global bot, users, cards, active_game_challenges, save_data, get_or_create_user
    global get_user_by_username, is_video_card, get_rarity_color, get_rarity_name
    global main_logger, add_event_score
    bot = bot_instance
    users = users_dict
    cards = cards_dict
    active_game_challenges = challenges_dict
    save_data = save_func
    get_or_create_user = get_user_func
    get_user_by_username = get_by_username_func
    is_video_card = is_video_func
    get_rarity_color = get_color_func
    get_rarity_name = get_name_func
    main_logger = logger_instance
    add_event_score = add_event_score_func or (lambda uid, t, n=1: None)


# ══════════════════════════════════════════
# Кубик удачи
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data == "game_lucky_dice")
async def game_lucky_dice_handler(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    if user.last_lucky_dice_time:
        last = datetime.fromisoformat(user.last_lucky_dice_time)
        remaining = timedelta(days=7) - (datetime.now() - last)
        if remaining.total_seconds() > 0:
            d, h = remaining.days, remaining.seconds // 3600
            await callback.answer(f"❌ Следующий бросок через {d}д {h}ч", show_alert=True)
            return
    # Отвечаем на callback ДО броска кубика — иначе "query too old"
    await callback.answer()
    # Бросаем кубик и ждём анимацию
    try:
        dice_msg = await callback.message.answer_dice(emoji="🎲")
        await asyncio.sleep(3)  # Ждём анимацию
        dice_value = dice_msg.dice.value
    except Exception as e:
        main_logger.error(f"Lucky dice error: {e}")
        dice_value = random.randint(1, 6)
    # Выдаём награду
    user.tokens += dice_value
    user.last_lucky_dice_time = datetime.now().isoformat()
    save_data()
    await callback.message.answer(
        f"🎲 <b>Кубик удачи!</b>\n\n"
        f"Выпало: <b>{dice_value}</b> {'🎉' if dice_value == 6 else ''}\n"
        f"Получено: <b>+{dice_value}🎫</b>\n"
        f"Баланс токенов: {user.tokens}🎫\n\n"
        f"<i>Следующий бросок — через 7 дней</i>"
    )


# ══════════════════════════════════════════
# Меню игр
# ══════════════════════════════════════════
@game_router.message(F.text == "Игры🕹")
async def games_menu_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id)
    lucky_available, lucky_cd = True, (0, 0)
    if user.last_lucky_dice_time:
        remaining = timedelta(days=7) - (datetime.now() - datetime.fromisoformat(user.last_lucky_dice_time))
        if remaining.total_seconds() > 0:
            lucky_available = False
            lucky_cd = (remaining.days, remaining.seconds // 3600)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🗿 Камень Ножницы Бумага", callback_data="game_rps"))
    keyboard.add(InlineKeyboardButton(text="🎲 Дайс", callback_data="game_dice"))
    keyboard.add(InlineKeyboardButton(text="🎰 Автоматы", callback_data="game_slots"))
    if lucky_available:
        keyboard.add(InlineKeyboardButton(text="🎲 Кубик удачи (раз в 7 дней)", callback_data="game_lucky_dice"))
    else:
        keyboard.add(InlineKeyboardButton(
            text=f"🎲 Кубик удачи (через {lucky_cd[0]}д {lucky_cd[1]}ч)",
            callback_data="game_lucky_dice"
        ))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    keyboard.adjust(1)

    total_wins = user.game_stats.total_wins()
    total_games = user.game_stats.total_games()
    winrate = user.game_stats.winrate()

    await message.answer(
        f"🎮 <b>Игры</b>\n\n"
        f"💰 Баланс токенов: {user.tokens}🎫\n"
        f"📊 Побед: {total_wins} / Игр: {total_games} (WR {winrate}%)\n\n"
        f"<b>Доступные игры:</b>\n"
        f"• 🗿 КНБ — против другого игрока\n"
        f"• 🎲 Дайс — кто выше кинет\n"
        f"• 🎰 Автоматы — кто выбьет комбинацию\n"
        f"• 🎲 Кубик удачи — токены раз в неделю\n\n"
        f"В каждой игре можно ставить карточки или токены.\nВыберите игру:",
        reply_markup=keyboard.as_markup()
    )


@game_router.callback_query(lambda c: c.data == "back_to_games")
async def back_to_games_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await games_menu_handler(callback.message)
    await callback.answer()


# ══════════════════════════════════════════
# Выбор типа ставки
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data in ["game_rps", "game_dice", "game_slots"])
async def game_type_handler(callback: types.CallbackQuery, state: FSMContext):
    game_type = callback.data.replace("game_", "")
    await state.update_data(game_type=game_type)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🎴 Играть на карточку", callback_data="game_bet_card"))
    keyboard.add(InlineKeyboardButton(text="🎫 Играть на токены", callback_data="game_bet_token"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_games"))
    keyboard.adjust(1)

    await callback.message.edit_text(
        f"<b>{game_names[game_type]}</b>\n\nВыберите, на что хотите играть:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(GameStates.choosing_bet_type)
    await callback.answer()


# ══════════════════════════════════════════
# Игра на карточку
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data == "game_bet_card", GameStates.choosing_bet_type)
async def game_bet_card_handler(callback: types.CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id)
    if not user.cards:
        await callback.answer("❌ У вас нет карточек для игры!", show_alert=True)
        return
    await state.update_data(bet_type="card")
    await callback.message.edit_text(
        "🎴 <b>Игра на карточку</b>\n\n"
        "Введите @username соперника:\n\n"
        "Или напишите /refresh для отмены"
    )
    await state.set_state(GameStates.choosing_opponent)
    await callback.answer()


# ══════════════════════════════════════════
# Игра на токены
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data == "game_bet_token", GameStates.choosing_bet_type)
async def game_bet_token_handler(callback: types.CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id)
    await state.update_data(bet_type="token")

    amounts = [1, 5, 10, 15, 20, 25, 30, 40, 50]
    keyboard = InlineKeyboardBuilder()
    for a in amounts:
        keyboard.add(InlineKeyboardButton(text=f"{a}🎫", callback_data=f"game_token_amount_{a}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_games"))
    keyboard.adjust(3)

    await callback.message.edit_text(
        f"🎫 <b>Игра на токены</b>\n\nВаш баланс: {user.tokens}🎫\n\nВыберите ставку:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(GameStates.choosing_bet_token_amount)
    await callback.answer()


@game_router.callback_query(lambda c: c.data.startswith("game_token_amount_"), GameStates.choosing_bet_token_amount)
async def game_token_amount_handler(callback: types.CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id)
    amount = int(callback.data.replace("game_token_amount_", ""))
    if user.tokens < amount:
        await callback.answer(f"❌ Недостаточно токенов! Нужно {amount}🎫", show_alert=True)
        return
    await state.update_data(bet_amount=amount)
    await callback.message.edit_text(
        f"🎫 <b>Игра на токены (ставка {amount}🎫)</b>\n\n"
        f"Введите @username соперника:\n\n"
        f"Или напишите /refresh для отмены"
    )
    await state.set_state(GameStates.choosing_opponent)
    await callback.answer()


# ══════════════════════════════════════════
# Ввод соперника
# ══════════════════════════════════════════
@game_router.message(GameStates.choosing_opponent)
async def game_process_opponent(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip('@')
    if username.lower() in ["/refresh", "отмена", "cancel", "stop", "стоп"]:
        await state.clear()
        await message.answer("✅ <b>Действие отменено!</b>")
        return
    opponent = get_user_by_username(username)
    if not opponent:
        await message.answer(f"❌ <b>Пользователь @{username} не найден!</b>\n\nПопробуйте еще раз или /refresh:")
        return
    if opponent.user_id == message.from_user.id:
        await message.answer("❌ <b>Нельзя играть с самим собой!</b>\n\nВведите другой username или /refresh:")
        return

    data = await state.get_data()
    game_type = data.get('game_type')
    bet_type = data.get('bet_type')
    bet_amount = data.get('bet_amount', 0)
    await state.update_data(opponent_id=opponent.user_id, opponent_username=opponent.username)

    if bet_type == "card":
        user = get_or_create_user(message.from_user.id)
        if not user.cards:
            await message.answer("❌ У вас нет карточек для игры!")
            await state.clear()
            return
        keyboard = InlineKeyboardBuilder()
        for card_id, quantity in user.cards.items():
            if quantity > 0:
                card = cards.get(card_id)
                if card:
                    icon = get_rarity_color(card.rarity)
                    video = "🎬 " if is_video_card(card) else ""
                    keyboard.add(InlineKeyboardButton(
                        text=f"{icon} {video}{card.name} (x{quantity})",
                        callback_data=f"game_select_card_{card_id}"
                    ))
        keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_games"))
        keyboard.adjust(1)
        await message.answer(
            f"🎴 <b>Выберите карту для ставки</b>\n\nСоперник: @{opponent.username}",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(GameStates.choosing_bet_card)
    else:
        challenger = get_or_create_user(message.from_user.id)
        if challenger.tokens < bet_amount:
            await message.answer(f"❌ У вас недостаточно токенов! Нужно {bet_amount}🎫")
            await state.clear()
            return
        if opponent.tokens < bet_amount:
            await message.answer(f"❌ У @{opponent.username} недостаточно токенов ({bet_amount}🎫)")
            await state.clear()
            return

        challenge_id = f"{game_type}_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
        challenge = GameChallenge(
            challenger_id=message.from_user.id,
            opponent_id=opponent.user_id,
            game_type=game_type,
            bet_type="token",
            bet_amount=bet_amount
        )
        active_game_challenges[challenge_id] = challenge

        await message.answer(
            f"✅ <b>Вызов отправлен!</b>\n\n"
            f"Игра: {game_names[game_type]}\n"
            f"Соперник: @{opponent.username}\n"
            f"Ставка: {bet_amount}🎫\n\n"
            f"Ожидайте ответа соперника..."
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"game_accept_{challenge_id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"game_reject_{challenge_id}"))
        try:
            await bot.send_message(
                opponent.user_id,
                f"🎮 <b>Вам брошен вызов!</b>\n\n"
                f"Игра: {game_names[game_type]}\n"
                f"От: @{message.from_user.username or 'игрок'}\n"
                f"Ставка: {bet_amount}🎫\n\n"
                f"У вас 5 минут чтобы принять или отклонить.",
                reply_markup=keyboard.as_markup()
            )
        except Exception as e:
            main_logger.error(f"Ошибка отправки вызова: {e}")
        await state.clear()


# ══════════════════════════════════════════
# Выбор карточки для ставки
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_select_card_"), GameStates.choosing_bet_card)
async def game_select_card_handler(callback: types.CallbackQuery, state: FSMContext):
    card_id = callback.data.replace("game_select_card_", "")
    user = get_or_create_user(callback.from_user.id)
    if card_id not in user.cards or user.cards[card_id] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True)
        return
    card = cards.get(card_id)
    if not card:
        await callback.answer("❌ Карточка не найдена", show_alert=True)
        return

    data = await state.get_data()
    game_type = data.get('game_type')
    opponent_id = data.get('opponent_id')
    opponent_username = data.get('opponent_username')
    if not opponent_id:
        await callback.answer("❌ Ошибка: соперник не найден", show_alert=True)
        await state.clear()
        return

    opponent = get_or_create_user(opponent_id)
    if not opponent.cards:
        await callback.answer(f"❌ У @{opponent_username} нет карточек!", show_alert=True)
        await state.clear()
        return

    challenge_id = f"{game_type}_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    challenge = GameChallenge(
        challenger_id=callback.from_user.id,
        opponent_id=opponent_id,
        game_type=game_type,
        bet_type="card",
        bet_amount=1,
        card_id=card_id
    )
    active_game_challenges[challenge_id] = challenge

    rarity_icon = get_rarity_color(card.rarity)
    video_icon = "🎬 " if is_video_card(card) else ""

    await callback.message.edit_text(
        f"✅ <b>Вызов отправлен!</b>\n\n"
        f"Игра: {game_names[game_type]}\n"
        f"Соперник: @{opponent_username}\n"
        f"Ваша ставка: {rarity_icon} {video_icon}{card.name}\n\n"
        f"Ожидайте ответа..."
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"game_accept_{challenge_id}"))
    keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"game_reject_{challenge_id}"))
    try:
        await bot.send_message(
            opponent_id,
            f"🎮 <b>Вам брошен вызов!</b>\n\n"
            f"Игра: {game_names[game_type]}\n"
            f"От: @{callback.from_user.username or 'игрок'}\n"
            f"Ставка: {rarity_icon} {video_icon}{card.name}\n\n"
            f"У вас 5 минут чтобы принять или отклонить.",
            reply_markup=keyboard.as_markup()
        )
    except Exception as e:
        main_logger.error(f"Ошибка отправки вызова: {e}")
    await state.clear()
    await callback.answer()


# ══════════════════════════════════════════
# Принятие вызова
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_accept_"))
async def game_accept_handler(callback: types.CallbackQuery, state: FSMContext):
    challenge_id = callback.data.replace("game_accept_", "")
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Вызов не найден или истёк.", show_alert=True)
        return
    if challenge.opponent_id != callback.from_user.id:
        await callback.answer("❌ Это не ваш вызов", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id)       # opponent
    challenger = get_or_create_user(challenge.challenger_id)

    # ── Проверка ставок ──────────────────────────────────────────
    if challenge.bet_type == "card":
        card = cards.get(challenge.card_id)
        if not card:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            del active_game_challenges[challenge_id]
            return
        if challenge.card_id not in challenger.cards or challenger.cards[challenge.card_id] <= 0:
            await callback.answer("❌ У соперника больше нет этой карточки!", show_alert=True)
            del active_game_challenges[challenge_id]
            return
        if not user.cards:
            await callback.answer("❌ У вас нет карточек для игры!", show_alert=True)
            return

        # Просим оппонента тоже поставить карту
        keyboard = InlineKeyboardBuilder()
        for cid, qty in user.cards.items():
            if qty > 0:
                c = cards.get(cid)
                if c:
                    icon = get_rarity_color(c.rarity)
                    keyboard.add(InlineKeyboardButton(
                        text=f"{icon} {c.name} (x{qty})",
                        callback_data=f"game_opp_card_{cid}_{challenge_id}"
                    ))
        keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"game_reject_{challenge_id}"))
        keyboard.adjust(1)

        rarity_icon = get_rarity_color(card.rarity)
        await callback.message.edit_text(
            f"🎴 <b>Выберите свою карточку для ставки</b>\n\n"
            f"Соперник ставит: {rarity_icon} {card.name}\n\n"
            f"Выберите карточку, которую поставите вы:",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        return

    else:  # token
        if user.tokens < challenge.bet_amount:
            await callback.answer(f"❌ Недостаточно токенов! Нужно {challenge.bet_amount}🎫", show_alert=True)
            return
        if challenger.tokens < challenge.bet_amount:
            await callback.answer("❌ У инициатора недостаточно токенов!", show_alert=True)
            del active_game_challenges[challenge_id]
            return
        # Резервируем токены
        user.tokens -= challenge.bet_amount
        challenger.tokens -= challenge.bet_amount
        save_data()

    # ── Запускаем игру ───────────────────────────────────────────
    challenge.status = 'accepted'
    challenge.accepted_at = datetime.now().isoformat()
    await callback.answer()  # Отвечаем ДО запуска
    asyncio.create_task(_start_game_send_buttons(challenge, challenge_id))


@game_router.callback_query(lambda c: c.data.startswith("game_opp_card_"))
async def game_opponent_card_select(callback: types.CallbackQuery):
    """Оппонент выбрал свою карту для ставки."""
    parts = callback.data.split("_")
    # game_opp_card_{card_id}_{challenge_id}
    # card_id может содержать _, поэтому разбираем иначе
    data_str = callback.data.replace("game_opp_card_", "", 1)
    # challenge_id - последний сегмент (содержит подчёркивания), известен формат:
    # gametype_timestamp_rand
    # Найдём challenge_id как последние 3 сегмента, разделённых _
    parts_all = data_str.split("_")
    challenge_id = "_".join(parts_all[-3:])
    opp_card_id = "_".join(parts_all[:-3])

    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Вызов истёк", show_alert=True)
        return
    if challenge.opponent_id != callback.from_user.id:
        await callback.answer("❌ Это не ваш вызов", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id)
    if opp_card_id not in user.cards or user.cards[opp_card_id] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True)
        return

    challenger = get_or_create_user(challenge.challenger_id)

    # Резервируем карты обоих игроков
    challenger.cards[challenge.card_id] = challenger.cards.get(challenge.card_id, 0) - 1
    if challenger.cards[challenge.card_id] <= 0:
        del challenger.cards[challenge.card_id]
    user.cards[opp_card_id] = user.cards.get(opp_card_id, 0) - 1
    if user.cards[opp_card_id] <= 0:
        del user.cards[opp_card_id]
    challenge.opponent_card_id = opp_card_id
    save_data()

    challenge.status = 'accepted'
    challenge.accepted_at = datetime.now().isoformat()

    opp_card = cards.get(opp_card_id)
    if opp_card:
        await callback.message.edit_text(
            f"✅ Вы поставили: {get_rarity_color(opp_card.rarity)} {opp_card.name}\n\nИгра начинается!"
        )

    # Уведомляем challenger'а что вызов принят
    try:
        await bot.send_message(
            challenge.challenger_id,
            f"✅ @{user.username} принял вызов!\n\nИгра: {game_names[challenge.game_type]}\nНачинается игра..."
        )
    except Exception:
        pass

    # Запускаем игру в фоне чтобы не блокировать callback
    asyncio.create_task(_start_game_send_buttons(challenge, challenge_id))



async def _start_game_send_buttons(challenge, challenge_id):
    """Рассылает кнопки для игры обоим игрокам."""
    if challenge.game_type == "rps":
        # Оба выбирают одновременно
        kb_opp = InlineKeyboardBuilder()
        kb_opp.add(InlineKeyboardButton(text="🗿 Камень", callback_data=f"game_choice_rps_opp_rock_{challenge_id}"))
        kb_opp.add(InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"game_choice_rps_opp_scissors_{challenge_id}"))
        kb_opp.add(InlineKeyboardButton(text="📄 Бумага", callback_data=f"game_choice_rps_opp_paper_{challenge_id}"))
        kb_opp.adjust(1)
        try:
            await bot.send_message(
                challenge.opponent_id,
                "🗿 <b>КНБ — Выберите вариант:</b>",
                reply_markup=kb_opp.as_markup()
            )
        except Exception:
            pass

        kb_cha = InlineKeyboardBuilder()
        kb_cha.add(InlineKeyboardButton(text="🗿 Камень", callback_data=f"game_choice_rps_cha_rock_{challenge_id}"))
        kb_cha.add(InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"game_choice_rps_cha_scissors_{challenge_id}"))
        kb_cha.add(InlineKeyboardButton(text="📄 Бумага", callback_data=f"game_choice_rps_cha_paper_{challenge_id}"))
        kb_cha.adjust(1)
        try:
            await bot.send_message(
                challenge.challenger_id,
                "🗿 <b>КНБ — Выберите вариант:</b>",
                reply_markup=kb_cha.as_markup()
            )
        except Exception:
            pass

    elif challenge.game_type == "dice":
        # Оппонент бросает первым (он уже здесь), потом challenger
        try:
            dice_msg = await bot.send_dice(challenge.opponent_id, emoji="🎲")
            await asyncio.sleep(3)
            challenge.opponent_choice = str(dice_msg.dice.value)
        except Exception:
            challenge.opponent_choice = str(random.randint(1, 6))

        kb_cha = InlineKeyboardBuilder()
        kb_cha.add(InlineKeyboardButton(text="🎲 Бросить кубик", callback_data=f"game_dice_roll_{challenge_id}"))
        try:
            await bot.send_message(
                challenge.challenger_id,
                f"🎲 <b>Дайс</b>\n\nСоперник бросил кубик. Теперь ваш ход!",
                reply_markup=kb_cha.as_markup()
            )
        except Exception:
            pass

    elif challenge.game_type == "slots":
        try:
            slots_msg = await bot.send_dice(challenge.opponent_id, emoji="🎰")
            await asyncio.sleep(3)
            dv = slots_msg.dice.value
            challenge.opponent_choice = _slots_value_to_result(dv)
            opp_symbols = challenge.opponent_choice.split(',')
            opp_win = opp_symbols[0] == opp_symbols[1] == opp_symbols[2]
            await bot.send_message(
                challenge.opponent_id,
                f"🎰 Ваш результат: {' '.join(opp_symbols)}\n{'🎉 ВЫИГРЫШ!' if opp_win else '❌ Не попал'}\nОжидайте соперника..."
            )
        except Exception:
            challenge.opponent_choice = "🍋,🍊,🍇"

        kb_cha = InlineKeyboardBuilder()
        kb_cha.add(InlineKeyboardButton(text="🎰 Крутить автомат", callback_data=f"game_slots_spin_{challenge_id}"))
        try:
            await bot.send_message(
                challenge.challenger_id,
                "🎰 <b>Автоматы</b>\n\nСоперник уже покрутил. Ваша очередь!",
                reply_markup=kb_cha.as_markup()
            )
        except Exception:
            pass


def _slots_value_to_result(dice_value: int) -> str:
    if dice_value == 1:   return '🍒,🍒,🍒'
    if dice_value == 22:  return '🍊,🍊,🍊'
    if dice_value == 43:  return '🍇,🍇,🍇'
    if dice_value == 64:  return '7️⃣,7️⃣,7️⃣'
    if dice_value == 65:  return '💎,💎,💎'
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    r = [random.choice(symbols) for _ in range(3)]
    while r[0] == r[1] == r[2]:
        r = [random.choice(symbols) for _ in range(3)]
    return ','.join(r)


# ══════════════════════════════════════════
# Отклонение вызова
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_reject_"))
async def game_reject_handler(callback: types.CallbackQuery):
    challenge_id = callback.data.replace("game_reject_", "")
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Вызов не найден", show_alert=True)
        return
    if challenge.opponent_id != callback.from_user.id:
        await callback.answer("❌ Это не ваш вызов", show_alert=True)
        return

    # Возвращаем ставки если были зарезервированы
    challenger = get_or_create_user(challenge.challenger_id)
    del active_game_challenges[challenge_id]

    await callback.message.edit_text("❌ Вы отклонили вызов.")
    try:
        await bot.send_message(challenge.challenger_id,
                               f"❌ @{callback.from_user.username or 'игрок'} отклонил ваш вызов.")
    except Exception:
        pass
    await callback.answer()


# ══════════════════════════════════════════
# КНБ — выборы
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_choice_rps_opp_"))
async def rps_opponent_choice(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    choice = parts[4]
    challenge_id = "_".join(parts[5:])
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Игра устарела", show_alert=True)
        return
    if challenge.opponent_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша игра", show_alert=True)
        return
    challenge.opponent_choice = choice
    await callback.message.edit_text(f"🗿 Вы выбрали: {RPS_ICONS.get(choice, choice)}\nОжидайте соперника...")
    await callback.answer()
    if challenge.challenger_choice:
        await determine_game_winner(challenge_id)


@game_router.callback_query(lambda c: c.data.startswith("game_choice_rps_cha_"))
async def rps_challenger_choice(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    choice = parts[4]
    challenge_id = "_".join(parts[5:])
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Игра устарела", show_alert=True)
        return
    if challenge.challenger_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша игра", show_alert=True)
        return
    challenge.challenger_choice = choice
    await callback.message.edit_text(f"🗿 Вы выбрали: {RPS_ICONS.get(choice, choice)}\nОжидайте соперника...")
    await callback.answer()
    if challenge.opponent_choice:
        await determine_game_winner(challenge_id)


# ══════════════════════════════════════════
# Дайс — бросок
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_dice_roll_"))
async def game_dice_roll_handler(callback: types.CallbackQuery):
    challenge_id = callback.data.replace("game_dice_roll_", "")
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Игра устарела", show_alert=True)
        return
    if challenge.challenger_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша игра", show_alert=True)
        return

    await callback.answer()  # отвечаем ДО sleep
    dice_msg = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(3)
    challenge.challenger_choice = str(dice_msg.dice.value)
    try:
        await callback.message.edit_text(
            f"🎲 Ваш бросок: <b>{dice_msg.dice.value}</b>\nОжидайте результатов..."
        )
    except Exception:
        pass
    await determine_game_winner(challenge_id)


# ══════════════════════════════════════════
# Слоты — вращение
# ══════════════════════════════════════════
@game_router.callback_query(lambda c: c.data.startswith("game_slots_spin_"))
async def game_slots_spin_handler(callback: types.CallbackQuery):
    challenge_id = callback.data.replace("game_slots_spin_", "")
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        await callback.answer("❌ Игра устарела", show_alert=True)
        return
    if challenge.challenger_id != callback.from_user.id:
        await callback.answer("❌ Это не ваша игра", show_alert=True)
        return

    await callback.answer()  # отвечаем ДО sleep
    slots_msg = await callback.message.answer_dice(emoji="🎰")
    await asyncio.sleep(3)
    result = _slots_value_to_result(slots_msg.dice.value)
    challenge.challenger_choice = result
    symbols = result.split(',')
    win = symbols[0] == symbols[1] == symbols[2]
    try:
        await callback.message.edit_text(
            f"🎰 Ваш результат: {' '.join(symbols)}\n{'🎉 ВЫИГРЫШ!' if win else '❌ Не попал'}\nОжидайте результатов..."
        )
    except Exception:
        pass
    await determine_game_winner(challenge_id)


# ══════════════════════════════════════════
# Определение победителя (ИСПРАВЛЕНО)
# ══════════════════════════════════════════
async def determine_game_winner(challenge_id: str):
    challenge = active_game_challenges.get(challenge_id)
    if not challenge:
        return
    if not challenge.challenger_choice or not challenge.opponent_choice:
        return

    user1 = get_or_create_user(challenge.challenger_id)   # challenger
    user2 = get_or_create_user(challenge.opponent_id)     # opponent

    result = None
    winner_id = None

    # ── КНБ ──
    if challenge.game_type == "rps":
        code = determine_rps_winner(challenge.challenger_choice, challenge.opponent_choice)
        if code == 0:
            result = "draw"
        elif code == 1:
            result = "challenger_win"; winner_id = challenge.challenger_id
        else:
            result = "opponent_win";  winner_id = challenge.opponent_id
        user1.game_stats.rock_paper_scissors['total'] += 1
        user2.game_stats.rock_paper_scissors['total'] += 1
        _update_stats(user1, user2, user1.game_stats.rock_paper_scissors, user2.game_stats.rock_paper_scissors, result)

    # ── Дайс ──
    elif challenge.game_type == "dice":
        c = int(challenge.challenger_choice)
        o = int(challenge.opponent_choice)
        if c == o:
            result = "draw"
        elif c > o:
            result = "challenger_win"; winner_id = challenge.challenger_id
        else:
            result = "opponent_win";  winner_id = challenge.opponent_id
        user1.game_stats.dice['total'] += 1
        user2.game_stats.dice['total'] += 1
        _update_stats(user1, user2, user1.game_stats.dice, user2.game_stats.dice, result)

    # ── Слоты ──
    elif challenge.game_type == "slots":
        c_syms = challenge.challenger_choice.split(',')
        o_syms = challenge.opponent_choice.split(',')
        c_win = c_syms[0] == c_syms[1] == c_syms[2]
        o_win = o_syms[0] == o_syms[1] == o_syms[2]
        if c_win == o_win:
            result = "draw"
        elif c_win:
            result = "challenger_win"; winner_id = challenge.challenger_id
        else:
            result = "opponent_win";  winner_id = challenge.opponent_id
        user1.game_stats.slots['total'] += 1
        user2.game_stats.slots['total'] += 1
        _update_stats(user1, user2, user1.game_stats.slots, user2.game_stats.slots, result)

    challenge.result = result
    challenge.winner_id = winner_id

    # ══ ОБРАБОТКА СТАВОК (ИСПРАВЛЕНО) ════════════════════
    # challenger_win → challenger получает приз (обе карты или возврат+токены)
    # opponent_win   → opponent получает приз
    # draw           → оба получают назад

    if challenge.bet_type == "card":
        c_card = cards.get(challenge.card_id)
        o_card = cards.get(challenge.opponent_card_id) if challenge.opponent_card_id else None

        if result == "challenger_win":
            # Challenger выиграл: получает свою карту обратно + карту оппонента (если была)
            user1.cards[challenge.card_id] = user1.cards.get(challenge.card_id, 0) + 1
            if o_card and challenge.opponent_card_id:
                user1.cards[challenge.opponent_card_id] = user1.cards.get(challenge.opponent_card_id, 0) + 1
        elif result == "opponent_win":
            # Opponent выиграл: получает карту challenger'а + свою обратно
            user2.cards[challenge.card_id] = user2.cards.get(challenge.card_id, 0) + 1
            if o_card and challenge.opponent_card_id:
                user2.cards[challenge.opponent_card_id] = user2.cards.get(challenge.opponent_card_id, 0) + 1
        else:  # draw
            # Ничья: каждый получает свою обратно
            user1.cards[challenge.card_id] = user1.cards.get(challenge.card_id, 0) + 1
            if challenge.opponent_card_id:
                user2.cards[challenge.opponent_card_id] = user2.cards.get(challenge.opponent_card_id, 0) + 1

    else:  # token
        if result == "challenger_win":
            user1.tokens += challenge.bet_amount * 2
        elif result == "opponent_win":
            user2.tokens += challenge.bet_amount * 2
        else:
            user1.tokens += challenge.bet_amount
            user2.tokens += challenge.bet_amount

    save_data()

    # Обновляем ивент "win_games"
    if result == "challenger_win":
        add_event_score(challenge.challenger_id, "win_games")
    elif result == "opponent_win":
        add_event_score(challenge.opponent_id, "win_games")

    # ── Текст результата ──────────────────────────────────────────
    c_card = cards.get(challenge.card_id)
    o_card_obj = cards.get(challenge.opponent_card_id) if challenge.opponent_card_id else None
    c_name = c_card.name if c_card else "карточка"
    o_name = o_card_obj.name if o_card_obj else None

    if challenge.bet_type == "card":
        if result == "draw":
            prize_info = "Ничья! Каждый забирает свою карточку."
        elif result == "challenger_win":
            prize_info = f"🏆 Победил @{user1.username}!\n" + \
                         (f"Приз: {c_name}" + (f" + {o_name}" if o_name else ""))
        else:
            prize_info = f"🏆 Победил @{user2.username}!\n" + \
                         (f"Приз: {c_name}" + (f" + {o_name}" if o_name else ""))
    else:
        if result == "draw":
            prize_info = f"Ничья! Ставки ({challenge.bet_amount}🎫) возвращены."
        elif result == "challenger_win":
            prize_info = f"🏆 Победил @{user1.username}! +{challenge.bet_amount*2}🎫"
        else:
            prize_info = f"🏆 Победил @{user2.username}! +{challenge.bet_amount*2}🎫"

    c_choice_text = _format_choice(challenge.game_type, challenge.challenger_choice)
    o_choice_text = _format_choice(challenge.game_type, challenge.opponent_choice)

    msg = (f"🎮 <b>Игра завершена!</b>\n\n"
           f"{prize_info}\n\n"
           f"@{user1.username}: {c_choice_text}\n"
           f"@{user2.username}: {o_choice_text}")

    try:
        await bot.send_message(challenge.challenger_id, msg)
    except Exception:
        pass
    try:
        await bot.send_message(challenge.opponent_id, msg)
    except Exception:
        pass

    if challenge_id in active_game_challenges:
        del active_game_challenges[challenge_id]


def _update_stats(u1, u2, s1, s2, result):
    if result == "draw":
        s1['draws'] += 1; s2['draws'] += 1
    elif result == "challenger_win":
        s1['wins'] += 1; s2['losses'] += 1
    else:
        s1['losses'] += 1; s2['wins'] += 1


def _format_choice(game_type: str, choice: str) -> str:
    if game_type == "rps":
        return RPS_ICONS.get(choice, choice)
    elif game_type == "dice":
        return f"🎲 {choice}"
    elif game_type == "slots":
        return ' '.join(choice.split(','))
    return choice
