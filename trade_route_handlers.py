# trade_route_handlers.py — Обмены и подарки (ПОЛНАЯ ПЕРЕПИСЬ)
import random
import logging
from datetime import datetime

from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import *
from states import TradeStates, GameStates

trade_router = Router()
router = trade_router
logger = logging.getLogger(__name__)

bot = None; users = None; cards = None; trades = None; save_data = None
get_or_create_user = None; get_user_by_username = None
check_access_before_handle = None; can_trade = None
add_experience = None; get_rarity_color = None; is_video_card = None
update_user_interaction = None; get_trade_cooldown_hours = None


def setup_trade_handlers(bot_i, users_d, cards_d, trades_d, save_fn,
                         get_user_fn, by_username_fn, access_fn, sub_fn,
                         can_trade_fn, add_exp_fn, rarity_color_fn, is_video_fn):
    global bot, users, cards, trades, save_data, get_or_create_user
    global get_user_by_username, check_access_before_handle, can_trade
    global add_experience, get_rarity_color, is_video_card
    global update_user_interaction, get_trade_cooldown_hours
    bot = bot_i; users = users_d; cards = cards_d; trades = trades_d
    save_data = save_fn; get_or_create_user = get_user_fn
    get_user_by_username = by_username_fn; check_access_before_handle = access_fn
    can_trade = can_trade_fn; add_experience = add_exp_fn
    get_rarity_color = rarity_color_fn; is_video_card = is_video_fn

    def _upd(u):
        now = datetime.now().isoformat()
        u.last_seen = now; u.last_interaction = now
    def _hours(u):
        if u.has_reduced_trade_cd and u.reduced_trade_cd_until:
            from datetime import datetime as dt
            if dt.fromisoformat(u.reduced_trade_cd_until) > dt.now(): return 2
        return 4
    globals()['update_user_interaction'] = _upd
    globals()['get_trade_cooldown_hours'] = _hours


@router.message(F.text == "🔄 Обмен")
async def trade_menu_handler(message: types.Message):
    if not await check_access_before_handle(message, message.from_user.id): return
    user = get_or_create_user(message.from_user.id, message.from_user.username or "")
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📝 Предложить обмен", callback_data="create_trade"))
    kb.add(InlineKeyboardButton(text="📨 Мои предложения", callback_data="my_trades"))
    kb.add(InlineKeyboardButton(text="📥 Входящие", callback_data="incoming_trades"))
    kb.add(InlineKeyboardButton(text="🎁 Подарить карточку", callback_data="gift_card"))
    kb.add(InlineKeyboardButton(text="❓ Как работает", callback_data="trade_help"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(2)
    can_now, remaining = can_trade(user)
    h = get_trade_cooldown_hours(user)
    status = "✅ Можно обмениваться" if can_now else f"⏰ Кулдаун: {remaining}"
    await message.answer(
        f"🔄 <b>Обмен карточками</b>\n\n"
        f"💼 Карточек: {len(user.cards)}\n"
        f"🕐 Кулдаун ({h}ч): {status}\n\nВыберите действие:",
        reply_markup=kb.as_markup()
    )


@router.callback_query(lambda c: c.data == "create_trade")
async def create_trade_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await check_access_before_handle(callback, callback.from_user.id): return
    user = get_or_create_user(callback.from_user.id)
    can_now, remaining = can_trade(user)
    if not can_now:
        await callback.answer(f"⏰ Кулдаун: {remaining}", show_alert=True); return
    if not user.cards:
        await callback.answer("🎴 У вас нет карточек!", show_alert=True); return
    await callback.message.answer(
        "📝 <b>Создание обмена</b>\n\nВведите @username партнёра:\n\n/refresh — отмена"
    )
    await state.set_state(TradeStates.selecting_partner)
    await callback.answer()


@router.message(TradeStates.selecting_partner)
async def trade_select_partner(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id):
        await state.clear(); return
    username = message.text.strip().lstrip('@')
    if username.lower() in ["/refresh", "отмена", "cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return
    partner = get_user_by_username(username)
    if not partner:
        await message.answer(f"❌ @{username} не найден. Попробуйте ещё или /refresh:"); return
    if partner.user_id == message.from_user.id:
        await message.answer("❌ Нельзя обмениваться с собой!"); return
    user = get_or_create_user(message.from_user.id)
    can_now, remaining = can_trade(user)
    if not can_now:
        await message.answer(f"⏰ Кулдаун: {remaining}"); await state.clear(); return
    await state.update_data(partner_id=partner.user_id, partner_username=partner.username)
    kb = InlineKeyboardBuilder()
    for cid, qty in user.cards.items():
        if qty > 0:
            c = cards.get(cid)
            if c:
                icon = get_rarity_color(c.rarity)
                vid = "🎬 " if is_video_card(c) else ""
                kb.add(InlineKeyboardButton(text=f"{icon} {vid}{c.name} (x{qty})",
                                            callback_data=f"select_trade_card_{cid}"))
    kb.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_trade_state"))
    kb.adjust(1)
    await message.answer(f"📝 Обмен с @{partner.username}\n\nВыберите вашу карточку:",
                         reply_markup=kb.as_markup())
    await state.set_state(TradeStates.selecting_my_cards)


@router.callback_query(lambda c: c.data.startswith("select_trade_card_"), TradeStates.selecting_my_cards)
async def select_trade_card_callback(callback: types.CallbackQuery, state: FSMContext):
    cid = callback.data.replace("select_trade_card_", "")
    user = get_or_create_user(callback.from_user.id)
    if cid not in user.cards or user.cards[cid] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True); return
    c = cards.get(cid)
    if not c:
        await callback.answer("❌ Карточка не найдена", show_alert=True); return
    data = await state.get_data()
    partner_id = data.get('partner_id'); partner_username = data.get('partner_username')
    if user.skip_trade_cooldown_available:
        user.skip_trade_cooldown_available = False
    else:
        user.last_trade_time = datetime.now().isoformat()
    update_user_interaction(user)
    trade_id = f"trade_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}"
    trades[trade_id] = {
        'id': trade_id, 'from_user': callback.from_user.id, 'to_user': partner_id,
        'cards': [cid], 'status': 'pending',
        'created_at': datetime.now().isoformat(), 'receiver_card': None, 'completed_at': None
    }
    save_data()
    icon = get_rarity_color(c.rarity)
    try:
        await callback.message.edit_text(
            f"✅ Предложение отправлено!\n👤 @{partner_username}\n🎴 {icon} {c.name}"
        )
    except Exception:
        await callback.message.answer(f"✅ Предложение @{partner_username} отправлено!")
    try:
        kb2 = InlineKeyboardBuilder()
        kb2.add(InlineKeyboardButton(text="👀 Просмотреть", callback_data=f"view_trade_{trade_id}"))
        await bot.send_message(partner_id,
            f"📥 <b>Предложение обмена!</b>\n👤 От: @{user.username}\n🎴 {icon} {c.name}\n\nОтветьте в 🔄 Обмен → Входящие",
            reply_markup=kb2.as_markup())
    except Exception as e: logger.error(f"Trade notify: {e}")
    await state.clear(); await callback.answer()


@router.callback_query(lambda c: c.data == "cancel_trade_state")
async def cancel_trade_state_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try: await callback.message.edit_text("❌ Отменено.")
    except Exception: await callback.message.answer("❌ Отменено.")
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_trades")
async def my_trades_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id): return
    uid = callback.from_user.id
    my = [t for t in trades.values() if t['from_user'] == uid and t['status'] == 'pending']
    if not my:
        await callback.message.answer("📨 Нет активных исходящих предложений."); await callback.answer(); return
    r = f"📨 <b>Исходящие ({len(my)}):</b>\n\n"
    for t in my[:10]:
        p = users.get(t['to_user']); pname = f"@{p.username}" if p else f"ID:{t['to_user']}"
        cnames = [f"{get_rarity_color(cards[ci].rarity)} {cards[ci].name}" for ci in t['cards'] if ci in cards]
        dt = datetime.fromisoformat(t['created_at']).strftime('%d.%m %H:%M')
        r += f"#{t['id'][-6:]} → {pname}\n🎴 {', '.join(cnames)}\n📅 {dt}\n\n"
    await callback.message.answer(r); await callback.answer()


@router.callback_query(lambda c: c.data == "incoming_trades")
async def incoming_trades_handler(callback: types.CallbackQuery):
    if not await check_access_before_handle(callback, callback.from_user.id): return
    uid = callback.from_user.id
    incoming = [t for t in trades.values() if t['to_user'] == uid and t['status'] == 'pending']
    if not incoming:
        await callback.message.answer("📥 Нет входящих предложений."); await callback.answer(); return
    kb = InlineKeyboardBuilder()
    r = f"📥 <b>Входящие ({len(incoming)}):</b>\n\n"
    for t in incoming[:10]:
        fu = users.get(t['from_user']); fname = f"@{fu.username}" if fu else f"ID:{t['from_user']}"
        cnames = [f"{get_rarity_color(cards[ci].rarity)} {cards[ci].name}" for ci in t['cards'] if ci in cards]
        dt = datetime.fromisoformat(t['created_at']).strftime('%d.%m %H:%M')
        r += f"#{t['id'][-6:]} от {fname}\n🎴 {', '.join(cnames)}\n📅 {dt}\n\n"
        kb.add(InlineKeyboardButton(text=f"👀 #{t['id'][-6:]} от {fname}", callback_data=f"view_trade_{t['id']}"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    kb.adjust(1)
    await callback.message.answer(r, reply_markup=kb.as_markup()); await callback.answer()


@router.callback_query(lambda c: c.data.startswith("view_trade_"))
async def view_trade_handler(callback: types.CallbackQuery):
    tid = callback.data.replace("view_trade_", "")
    if tid not in trades:
        await callback.answer("❌ Обмен не найден или завершён", show_alert=True); return
    t = trades[tid]
    fu = users.get(t['from_user']); tu = users.get(t['to_user'])
    fname = f"@{fu.username}" if fu else f"ID:{t['from_user']}"
    tname = f"@{tu.username}" if tu else f"ID:{t['to_user']}"
    r = f"🔄 <b>Обмен #{tid[-6:]}</b>\n👤 От: {fname}\n👤 Кому: {tname}\n\n<b>Предлагаемые карточки:</b>\n"
    for ci in t['cards']:
        c = cards.get(ci)
        if c: r += f"{get_rarity_color(c.rarity)} {'🎬 ' if is_video_card(c) else ''}{c.name}\n"
    kb = InlineKeyboardBuilder()
    if callback.from_user.id == t['to_user']:
        kb.add(InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_trade_{tid}"))
        kb.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_trade_{tid}"))
    kb.add(InlineKeyboardButton(text="🔙 Назад", callback_data="incoming_trades"))
    kb.adjust(2)
    try: await callback.message.edit_text(r, reply_markup=kb.as_markup())
    except Exception: await callback.message.answer(r, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("accept_trade_"))
async def accept_trade_handler(callback: types.CallbackQuery):
    tid = callback.data.replace("accept_trade_", "")
    if tid not in trades:
        await callback.answer("❌ Обмен не найден", show_alert=True); return
    t = trades[tid]
    if callback.from_user.id != t['to_user']:
        await callback.answer("❌ Это не ваш обмен", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    can_now, remaining = can_trade(user)
    if not can_now:
        await callback.answer(f"⏰ Кулдаун: {remaining}", show_alert=True); return
    from_user = get_or_create_user(t['from_user'])
    for ci in t['cards']:
        if from_user.cards.get(ci, 0) <= 0:
            await callback.answer("❌ Инициатор уже не имеет этих карточек", show_alert=True)
            t['status'] = 'cancelled'; save_data(); return
    if not user.cards:
        await callback.answer("❌ У вас нет карточек для ответного обмена", show_alert=True); return
    kb = InlineKeyboardBuilder()
    for ci, qty in user.cards.items():
        if qty > 0:
            c = cards.get(ci)
            if c:
                icon = get_rarity_color(c.rarity)
                vid = "🎬 " if is_video_card(c) else ""
                kb.add(InlineKeyboardButton(text=f"{icon} {vid}{c.name} (x{qty})",
                                            callback_data=f"trade_give_card_{tid}_{ci}"))
    kb.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"reject_trade_{tid}"))
    kb.adjust(1)
    try: await callback.message.edit_text("✅ Принять обмен!\n\nВыберите карточку взамен:", reply_markup=kb.as_markup())
    except Exception: await callback.message.answer("Выберите карточку взамен:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("trade_give_card_"))
async def trade_give_card_handler(callback: types.CallbackQuery):
    raw = callback.data.replace("trade_give_card_", "", 1)
    parts = raw.split("_")
    # trade_id = trade_TIMESTAMP_RAND = 3 parts
    trade_id = "_".join(parts[:3])
    receiver_card_id = "_".join(parts[3:])
    if trade_id not in trades:
        await callback.answer("❌ Обмен не найден", show_alert=True); return
    t = trades[trade_id]
    if callback.from_user.id != t['to_user']:
        await callback.answer("❌ Это не ваш обмен", show_alert=True); return
    user = get_or_create_user(callback.from_user.id)
    from_user = get_or_create_user(t['from_user'])
    if receiver_card_id not in user.cards or user.cards[receiver_card_id] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True); return
    for ci in t['cards']:
        if from_user.cards.get(ci, 0) <= 0:
            await callback.answer("❌ Инициатор уже не имеет своих карточек", show_alert=True)
            t['status'] = 'cancelled'; save_data(); return
    # Передаём карточки
    for ci in t['cards']:
        from_user.cards[ci] = from_user.cards.get(ci, 0) - 1
        if from_user.cards[ci] <= 0: del from_user.cards[ci]
        user.cards[ci] = user.cards.get(ci, 0) + 1
    user.cards[receiver_card_id] -= 1
    if user.cards[receiver_card_id] <= 0: del user.cards[receiver_card_id]
    from_user.cards[receiver_card_id] = from_user.cards.get(receiver_card_id, 0) + 1
    if user.skip_trade_cooldown_available: user.skip_trade_cooldown_available = False
    else: user.last_trade_time = datetime.now().isoformat()
    if from_user.skip_trade_cooldown_available: from_user.skip_trade_cooldown_available = False
    else: from_user.last_trade_time = datetime.now().isoformat()
    t['status'] = 'completed'; t['receiver_card'] = receiver_card_id
    t['completed_at'] = datetime.now().isoformat()
    add_experience(user, 'trade_complete'); add_experience(from_user, 'trade_complete')
    update_user_interaction(user); update_user_interaction(from_user)
    save_data()
    given = [f"{get_rarity_color(cards[ci].rarity)} {cards[ci].name}" for ci in t['cards'] if ci in cards]
    rc = cards.get(receiver_card_id)
    rname = f"{get_rarity_color(rc.rarity)} {rc.name}" if rc else receiver_card_id
    try: await callback.message.edit_text(f"✅ <b>Обмен завершён!</b>\nВы получили: {', '.join(given)}\nВы отдали: {rname}")
    except Exception: await callback.message.answer(f"✅ Обмен завершён! Получили: {', '.join(given)}")
    try:
        await bot.send_message(from_user.user_id,
            f"✅ <b>Обмен завершён!</b>\n👤 С: @{user.username}\n"
            f"Вы получили: {rname}\nВы отдали: {', '.join(given)}")
    except Exception: pass
    await callback.answer("✅ Обмен завершён!")


@router.callback_query(lambda c: c.data.startswith("reject_trade_"))
async def reject_trade_handler(callback: types.CallbackQuery):
    tid = callback.data.replace("reject_trade_", "")
    if tid not in trades:
        await callback.answer("❌ Обмен не найден", show_alert=True); return
    t = trades[tid]
    if callback.from_user.id != t['to_user']:
        await callback.answer("❌ Это не ваш обмен", show_alert=True); return
    t['status'] = 'rejected'; t['completed_at'] = datetime.now().isoformat()
    save_data()
    try: await callback.message.edit_text(f"❌ Обмен #{tid[-6:]} отклонён.")
    except Exception: await callback.message.answer("❌ Обмен отклонён.")
    try:
        fu = users.get(t['from_user'])
        if fu:
            await bot.send_message(fu.user_id,
                f"❌ @{callback.from_user.username} отклонил обмен #{tid[-6:]}.")
    except Exception: pass
    await callback.answer("❌ Отклонено.")


@router.callback_query(lambda c: c.data == "gift_card")
async def gift_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await check_access_before_handle(callback, callback.from_user.id): return
    user = get_or_create_user(callback.from_user.id)
    if not user.cards:
        await callback.answer("🎴 У вас нет карточек!", show_alert=True); return
    kb = InlineKeyboardBuilder()
    for cid, qty in user.cards.items():
        if qty > 0:
            c = cards.get(cid)
            if c:
                kb.add(InlineKeyboardButton(text=f"{get_rarity_color(c.rarity)} {c.name} (x{qty})",
                                            callback_data=f"gift_select_card_{cid}"))
    kb.add(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu"))
    kb.adjust(1)
    try: await callback.message.edit_text("🎁 <b>Подарок</b>\n\nВыберите карточку:", reply_markup=kb.as_markup())
    except Exception: await callback.message.answer("🎁 Выберите карточку:", reply_markup=kb.as_markup())
    await state.set_state(GameStates.gifting_card_select)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("gift_select_card_"), GameStates.gifting_card_select)
async def gift_select_card_handler(callback: types.CallbackQuery, state: FSMContext):
    cid = callback.data.replace("gift_select_card_", "")
    user = get_or_create_user(callback.from_user.id)
    if cid not in user.cards or user.cards[cid] <= 0:
        await callback.answer("❌ У вас нет этой карточки!", show_alert=True); return
    c = cards.get(cid)
    if not c:
        await callback.answer("❌ Карточка не найдена", show_alert=True); return
    await state.update_data(gift_card_id=cid)
    icon = get_rarity_color(c.rarity)
    try: await callback.message.edit_text(f"🎁 Выбрана: {icon} {c.name}\n\nВведите @username получателя:")
    except Exception: await callback.message.answer(f"🎁 {icon} {c.name} — введите @username:")
    await state.set_state(GameStates.gifting_card_username)
    await callback.answer()


@router.message(GameStates.gifting_card_username)
async def gift_process_username(message: types.Message, state: FSMContext):
    if not await check_access_before_handle(message, message.from_user.id):
        await state.clear(); return
    username = message.text.strip().lstrip('@')
    if username.lower() in ["/refresh", "отмена", "cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return
    partner = get_user_by_username(username)
    if not partner:
        await message.answer(f"❌ @{username} не найден. Попробуйте ещё или /refresh:"); return
    if partner.user_id == message.from_user.id:
        await message.answer("❌ Нельзя дарить самому себе!"); return
    data = await state.get_data()
    cid = data.get('gift_card_id')
    if not cid:
        await message.answer("❌ Ошибка: карточка не выбрана."); await state.clear(); return
    user = get_or_create_user(message.from_user.id)
    if cid not in user.cards or user.cards[cid] <= 0:
        await message.answer("❌ У вас больше нет этой карточки!"); await state.clear(); return
    c = cards.get(cid)
    if not c:
        await message.answer("❌ Карточка не найдена."); await state.clear(); return
    user.cards[cid] -= 1
    if user.cards[cid] <= 0: del user.cards[cid]
    partner.cards[cid] = partner.cards.get(cid, 0) + 1
    update_user_interaction(user); update_user_interaction(partner)
    save_data()
    icon = get_rarity_color(c.rarity)
    await message.answer(f"✅ <b>Подарок отправлен!</b>\n🎁 {icon} {c.name}\n👤 @{partner.username}")
    try:
        await bot.send_message(partner.user_id,
            f"🎁 <b>Вам подарили карточку!</b>\n👤 От: @{user.username}\n🎴 {icon} {c.name}")
    except Exception: pass
    await state.clear()


@router.callback_query(lambda c: c.data == "trade_help")
async def trade_help_handler(callback: types.CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    h = get_trade_cooldown_hours(user)
    await callback.message.answer(
        f"❓ <b>Как работает обмен</b>\n\n"
        f"1. Предложите обмен → выберите карточку → введите @username\n"
        f"2. Партнёр видит предложение и выбирает свою карточку взамен\n"
        f"3. Карточки меняются!\n\n"
        f"🎁 Подарок — безвозмездно, без кулдауна\n\n"
        f"⏰ Кулдаун: {h} часа | 💡 Скип кулдауна — в магазине"
    )
    await callback.answer()
