# admin_handlers.py — Панель администратора (ИСПРАВЛЕНО)
import asyncio
import json
import os
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import *
from states import AdminStates
from promo import PromoCodeManager

admin_router = Router()
router = admin_router   # ← КРИТИЧЕСКИЙ ФИКС: все @router. теперь работают

logger = logging.getLogger(__name__)

# ─── Глобальные переменные ───
bot = None
users = None
cards = None
card_pool = None
trades = None
shop_items = None
orders = None
exclusive_cards = None
promo_manager = None
current_wheel = None
save_data = None
load_data = None
get_or_create_user = None
get_user_by_username = None
update_user_interaction = None
add_premium = None
add_reduced_cd = None
add_reduced_trade_cd = None
add_cooldown = None
update_card_pool = None
get_rarity_color = None
get_rarity_name = None
is_video_card = None
get_image_path = None
get_video_path = None
ban_user = None
confirm_order = None
reject_order = None
send_order_notification = None
get_top_spenders = None
DATA_DIR = None
IMAGES_DIR = None
VIDEOS_DIR = None
USERS_FILE = None
Card = None


def setup_admin_handlers(bot_i, users_d, cards_d, card_pool_r, trades_d,
                         shop_d, orders_d, excl_d, promo_m, wheel_r,
                         save_fn, load_fn, get_user_fn, by_username_fn,
                         update_user_fn,
                         add_premium_fn, add_red_cd_fn, add_red_tcd_fn,
                         add_cd_fn, upd_pool_fn,
                         rarity_color_fn, rarity_name_fn,
                         is_video_fn, img_path_fn, vid_path_fn,
                         ban_fn, confirm_order_fn, reject_order_fn,
                         order_notif_fn, top_spenders_fn,
                         data_dir, images_dir, videos_dir,
                         users_file, card_class):
    global bot, users, cards, card_pool, trades, shop_items, orders, exclusive_cards
    global promo_manager, current_wheel, save_data, load_data
    global get_or_create_user, get_user_by_username, update_user_interaction
    global add_premium, add_reduced_cd, add_reduced_trade_cd, add_cooldown, update_card_pool
    global get_rarity_color, get_rarity_name, is_video_card, get_image_path, get_video_path
    global ban_user, confirm_order, reject_order, send_order_notification, get_top_spenders
    global DATA_DIR, IMAGES_DIR, VIDEOS_DIR, USERS_FILE, Card
    bot = bot_i; users = users_d; cards = cards_d; card_pool = card_pool_r
    trades = trades_d; shop_items = shop_d; orders = orders_d; exclusive_cards = excl_d
    promo_manager = promo_m; current_wheel = wheel_r
    save_data = save_fn; load_data = load_fn
    get_or_create_user = get_user_fn; get_user_by_username = by_username_fn
    update_user_interaction = update_user_fn
    add_premium = add_premium_fn; add_reduced_cd = add_red_cd_fn
    add_reduced_trade_cd = add_red_tcd_fn; add_cooldown = add_cd_fn
    update_card_pool = upd_pool_fn
    get_rarity_color = rarity_color_fn; get_rarity_name = rarity_name_fn
    is_video_card = is_video_fn; get_image_path = img_path_fn; get_video_path = vid_path_fn
    ban_user = ban_fn; confirm_order = confirm_order_fn; reject_order = reject_order_fn
    send_order_notification = order_notif_fn; get_top_spenders = top_spenders_fn
    DATA_DIR = data_dir; IMAGES_DIR = images_dir; VIDEOS_DIR = videos_dir
    USERS_FILE = users_file; Card = card_class


# ══════════════════════════════════════════
# Главное меню
# ══════════════════════════════════════════
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ <b>Нет доступа.</b>")
        return
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="➕ Добавить карточку", callback_data="admin_add_card"))
    keyboard.add(InlineKeyboardButton(text="🗑️ Удалить карточку", callback_data="admin_delete_card"))
    keyboard.add(InlineKeyboardButton(text="💎 Выдать премиум", callback_data="admin_give_premium"))
    keyboard.add(InlineKeyboardButton(text="⚡ Сбросить кулдаун", callback_data="admin_reset_cooldown"))
    keyboard.add(InlineKeyboardButton(text="⏰ Добавить кулдаун", callback_data="admin_add_cooldown"))
    keyboard.add(InlineKeyboardButton(text="⚡ Уменьш. кулдаун карт", callback_data="admin_give_reduced_cd"))
    keyboard.add(InlineKeyboardButton(text="🔄 Уменьш. кулдаун обменов", callback_data="admin_give_reduced_trade_cd"))
    keyboard.add(InlineKeyboardButton(text="🎁 Выдать карточку", callback_data="admin_give_card_by_id"))
    keyboard.add(InlineKeyboardButton(text="🎬 Добавить видео карточку", callback_data="admin_add_video_card"))
    keyboard.add(InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders"))
    keyboard.add(InlineKeyboardButton(text="⛔ Забанить", callback_data="admin_ban_user"))
    keyboard.add(InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban_user"))
    keyboard.add(InlineKeyboardButton(text="❄️ Заморозить", callback_data="admin_freeze_user"))
    keyboard.add(InlineKeyboardButton(text="☀️ Разморозить", callback_data="admin_unfreeze_user"))
    keyboard.add(InlineKeyboardButton(text="⚙️ Система уровней", callback_data="admin_level_system"))
    keyboard.add(InlineKeyboardButton(text="📥 База данных", callback_data="admin_database"))
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить пул", callback_data="admin_update_pool"))
    keyboard.add(InlineKeyboardButton(text="🎫 Создать промо", callback_data="admin_create_promo"))
    keyboard.add(InlineKeyboardButton(text="🎁 Выдать токены", callback_data="admin_give_tokens"))
    keyboard.add(InlineKeyboardButton(text="🔄 Перезапуск", callback_data="admin_restart"))
    keyboard.adjust(2)
    await message.answer("⚙️ <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=keyboard.as_markup())


# ══════════════════════════════════════════
# Рассылка
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("📢 <b>Рассылка</b>\n\nОтправьте текст/фото/видео для рассылки:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast, F.text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    sent, fail = 0, 0
    for uid, user in users.items():
        if user.is_banned or user.is_frozen: continue
        try:
            await bot.send_message(uid, message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await message.answer(f"✅ Рассылка завершена!\nОтправлено: {sent}, ошибок: {fail}")
    await state.clear()

@router.message(AdminStates.waiting_for_broadcast, F.photo)
async def process_broadcast_photo(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    sent, fail = 0, 0
    for uid, user in users.items():
        if user.is_banned or user.is_frozen: continue
        try:
            await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            sent += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await message.answer(f"✅ Рассылка завершена!\nОтправлено: {sent}, ошибок: {fail}")
    await state.clear()

@router.message(AdminStates.waiting_for_broadcast, F.video)
async def process_broadcast_video(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    sent, fail = 0, 0
    for uid, user in users.items():
        if user.is_banned or user.is_frozen: continue
        try:
            await bot.send_video(uid, message.video.file_id, caption=message.caption or "")
            sent += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await message.answer(f"✅ Рассылка завершена!\nОтправлено: {sent}, ошибок: {fail}")
    await state.clear()


# ══════════════════════════════════════════
# Статистика
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    total = len(users)
    active_today = sum(1 for u in users.values() if u.last_seen and (datetime.now()-datetime.fromisoformat(u.last_seen)).days < 1)
    active_week = sum(1 for u in users.values() if u.last_seen and (datetime.now()-datetime.fromisoformat(u.last_seen)).days < 7)
    total_tokens = sum(u.tokens for u in users.values())
    pending = sum(1 for o in orders.values() if o.status == "pending")
    confirmed = sum(1 for o in orders.values() if o.status == "confirmed")
    revenue = sum(o.price for o in orders.values() if o.status == "confirmed")
    await callback.message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: {total} (сегодня: {active_today}, неделя: {active_week})\n"
        f"🎴 Карточек в системе: {len(cards)}\n"
        f"🎫 Токенов в обороте: {total_tokens}\n"
        f"📦 Заказов: {len(orders)} (ожид: {pending}, подтв: {confirmed})\n"
        f"💰 Выручка: {revenue}₽"
    )
    await callback.answer()


# ══════════════════════════════════════════
# Добавление карточек
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_add_video_card")
async def admin_add_video_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("🎬 <b>Добавление видео карточки</b>\n\nВведите название:")
    await state.set_state(AdminStates.waiting_for_card_name)
    await state.update_data(is_video=True)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_add_card")
async def admin_add_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("➕ <b>Добавление карточки</b>\n\nВведите название:")
    await state.set_state(AdminStates.waiting_for_card_name)
    await state.update_data(is_video=False)
    await callback.answer()

@router.message(AdminStates.waiting_for_card_name)
async def process_card_name(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    await state.update_data(card_name=message.text)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⚪️ Обычная", callback_data="rarity_basic"))
    keyboard.add(InlineKeyboardButton(text="🔵 Крутая", callback_data="rarity_cool"))
    keyboard.add(InlineKeyboardButton(text="🟡 Легендарная", callback_data="rarity_legendary"))
    keyboard.add(InlineKeyboardButton(text="🟣 Виниловая", callback_data="rarity_vinyl figure"))
    keyboard.adjust(2)
    await message.answer(f"Название: <b>{message.text}</b>\n\nВыберите редкость:", reply_markup=keyboard.as_markup())
    await state.set_state(AdminStates.waiting_for_card_rarity)

@router.callback_query(lambda c: c.data.startswith("rarity_"))
async def process_card_rarity(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await state.clear(); return
    rarity = callback.data.replace("rarity_", "")
    await state.update_data(card_rarity=rarity)
    data = await state.get_data()
    is_video = data.get('is_video', False)
    await callback.message.edit_text(
        f"Название: <b>{data.get('card_name')}</b>\nРедкость: <b>{get_rarity_name(rarity)}</b>\n\n"
        f"Отправьте {'видео (MP4)' if is_video else 'изображение'} или нажмите Пропустить:"
    )
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_image"))
    await callback.message.answer("Выберите:", reply_markup=keyboard.as_markup())
    await state.set_state(AdminStates.waiting_for_card_image)
    await callback.answer()

@router.callback_query(lambda c: c.data == "skip_image", AdminStates.waiting_for_card_image)
async def skip_card_image(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await _complete_card_add(callback.message, state, data, "")
    await callback.answer()

@router.message(AdminStates.waiting_for_card_image, F.photo)
async def process_card_image_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get('is_video'):
        await message.answer("❌ Ожидалось видео, но получено фото. Пропустите или отправьте MP4.")
        return
    try:
        photo = message.photo[-1]
        photo_file = await bot.get_file(photo.file_id)
        card_id = f"card_{int(datetime.now().timestamp())}"
        photo_path = IMAGES_DIR / f"{card_id}.jpg"
        await bot.download_file(photo_file.file_path, photo_path)
        await _complete_card_add(message, state, data, f"{card_id}.jpg")
    except Exception as e:
        logger.error(f"Ошибка сохранения изображения: {e}")
        await _complete_card_add(message, state, data, "")

@router.message(AdminStates.waiting_for_card_image, F.video)
async def process_card_image_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('is_video'):
        await message.answer("❌ Ожидалось фото, но получено видео. Пропустите или отправьте фото.")
        return
    try:
        video = message.video
        video_file = await bot.get_file(video.file_id)
        card_id = f"card_{int(datetime.now().timestamp())}"
        video_path = VIDEOS_DIR / f"{card_id}.mp4"
        await bot.download_file(video_file.file_path, video_path)
        await _complete_card_add(message, state, data, f"{card_id}.mp4")
    except Exception as e:
        logger.error(f"Ошибка сохранения видео: {e}")
        await _complete_card_add(message, state, data, "")

async def _complete_card_add(source, state, data, image_filename):
    card_name = data.get('card_name')
    card_rarity = data.get('card_rarity')
    is_video = data.get('is_video', False)
    card_id = f"card_{int(datetime.now().timestamp())}"
    cards[card_id] = Card(card_id=card_id, name=card_name, rarity=card_rarity, image_filename=image_filename)
    update_card_pool()
    save_data()
    text = (
        f"✅ <b>Карточка добавлена!</b>\n\n"
        f"🎴 {card_name}\n"
        f"📊 {get_rarity_name(card_rarity)}\n"
        f"🆔 <code>{card_id}</code>\n"
        f"{'🎬 Видео' if is_video else '🖼 Изображение'}: {'✅' if image_filename else '❌'}\n"
        f"Всего карточек: {len(cards)}"
    )
    if isinstance(source, types.Message):
        await source.answer(text)
    else:
        await source.answer(text)
    await state.clear()


# ══════════════════════════════════════════
# Удаление карточки
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_delete_card")
async def admin_delete_card_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    cards_list = "\n".join([f"<code>{cid}</code>: {c.name} ({c.rarity})" for cid, c in cards.items()])
    await callback.message.answer(f"🗑️ <b>Удаление карточки</b>\n\n{cards_list}\n\nВведите ID карточки:")
    await state.set_state(AdminStates.waiting_for_card_id_to_delete)
    await callback.answer()

@router.message(AdminStates.waiting_for_card_id_to_delete)
async def process_delete_card(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    card_id = message.text.strip()
    if card_id not in cards:
        await message.answer(f"❌ Карточка '{card_id}' не найдена."); await state.clear(); return
    card = cards[card_id]
    if card.image_filename:
        fp = (VIDEOS_DIR if is_video_card(card) else IMAGES_DIR) / card.image_filename
        if fp.exists():
            try: os.remove(fp)
            except: pass
    del cards[card_id]
    update_card_pool()
    save_data()
    await message.answer(f"✅ Карточка <b>{card.name}</b> удалена. Осталось: {len(cards)}")
    await state.clear()


# ══════════════════════════════════════════
# Выдача премиума
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_give_premium")
async def admin_give_premium_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("💎 <b>Выдача премиума</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_premium_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_premium_username)
async def process_premium_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    add_premium(user, days=30)
    await message.answer(f"✅ Премиум на 30 дней выдан @{user.username}!")
    try:
        await bot.send_message(user.user_id,
            "🎉 <b>Вам выдан премиум на 30 дней!</b>\n\n"
            "• Удвоенный шанс на редкие карты\n• 3 токена за карточку\n• Ежедневный бонус")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# Кулдауны
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_reset_cooldown")
async def admin_reset_cooldown_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("⚡ <b>Сброс кулдауна</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_cooldown_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_cooldown_username)
async def process_cooldown_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    user.last_card_time = None; user.last_trade_time = None
    update_user_interaction(user)
    await message.answer(f"✅ Кулдауны сброшены для @{user.username}!")
    try:
        await bot.send_message(user.user_id, "⚡ Ваши кулдауны сброшены администратором!")
    except: pass
    await state.clear()

@router.callback_query(lambda c: c.data == "admin_add_cooldown")
async def admin_add_cooldown_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("⏰ <b>Добавление кулдауна</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_add_cooldown_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_add_cooldown_username)
async def process_add_cooldown(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    user.last_card_time = datetime.now().isoformat()
    update_user_interaction(user)
    await message.answer(f"✅ Кулдаун 4ч установлен для @{user.username}!")
    await state.clear()

@router.callback_query(lambda c: c.data == "admin_give_reduced_cd")
async def admin_give_reduced_cd_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("⚡ <b>Уменьшенный кулдаун карточек</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_reduced_cd_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_reduced_cd_username)
async def process_reduced_cd(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    add_reduced_cd(user, days=30)
    await message.answer(f"✅ Уменьшенный кулдаун карточек (2ч) на 30 дней выдан @{user.username}!")
    try:
        await bot.send_message(user.user_id, "🎉 Вам выдан уменьшенный кулдаун карточек (2ч) на 30 дней!")
    except: pass
    await state.clear()

@router.callback_query(lambda c: c.data == "admin_give_reduced_trade_cd")
async def admin_give_reduced_trade_cd_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("🔄 <b>Уменьшенный кулдаун обменов</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_reduced_trade_cd_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_reduced_trade_cd_username)
async def process_reduced_trade_cd(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    add_reduced_trade_cd(user, days=30)
    await message.answer(f"✅ Уменьшенный кулдаун обменов (2ч) на 30 дней выдан @{user.username}!")
    try:
        await bot.send_message(user.user_id, "🎉 Вам выдан уменьшенный кулдаун обменов (2ч) на 30 дней!")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# Выдача карточки по ID
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_give_card_by_id")
async def admin_give_card_by_id_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("🎁 <b>Выдача карточки</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_give_card_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_give_card_username)
async def process_give_card_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    if not user:
        await message.answer(f"❌ @{username} не найден."); return
    await state.update_data(target_user_id=user.user_id, target_username=username)
    cards_list = "\n".join([f"<code>{cid}</code>: {c.name} ({get_rarity_name(c.rarity)})" for cid, c in cards.items()])
    await message.answer(f"✅ Пользователь: @{username}\n\n<b>Карточки:</b>\n{cards_list}\n\nВведите ID карточки:")
    await state.set_state(AdminStates.waiting_for_give_card_id)

@router.message(AdminStates.waiting_for_give_card_id)
async def process_give_card_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    card_id = message.text.strip()
    if card_id not in cards:
        await message.answer(f"❌ Карточка '{card_id}' не найдена."); return
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    user = users.get(target_user_id)
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    card = cards[card_id]
    user.cards[card_id] = user.cards.get(card_id, 0) + 1
    update_user_interaction(user)
    save_data()
    await message.answer(f"✅ {card.name} выдана @{user.username}!")
    try:
        await bot.send_message(user.user_id,
            f"🎁 Вам выдана карточка администратором!\n\n🎴 {card.name} ({get_rarity_name(card.rarity)})")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# Заказы
# ══════════════════════════════════════════
def _order_card_name(order):
    if order.card_id == "skip_card_cooldown": return "⚡ Скип кулдауна карточки"
    if order.card_id == "skip_trade_cooldown": return "🔄 Скип кулдауна обменов"
    if order.card_id == "buy_level_1": return "🎮 +1 уровень"
    if order.card_id == "buy_level_5": return "🎮 +5 уровней"
    card = cards.get(order.card_id)
    return card.name if card else "Неизвестный товар"

@router.callback_query(lambda c: c.data == "admin_orders")
async def admin_orders_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    pending = sum(1 for o in orders.values() if o.status == "pending")
    confirmed = sum(1 for o in orders.values() if o.status == "confirmed")
    rejected = sum(1 for o in orders.values() if o.status == "rejected")
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f"⏳ Ожидают ({pending})", callback_data="admin_orders_pending"))
    keyboard.add(InlineKeyboardButton(text=f"✅ Подтверждённые ({confirmed})", callback_data="admin_orders_confirmed"))
    keyboard.add(InlineKeyboardButton(text=f"❌ Отклонённые ({rejected})", callback_data="admin_orders_rejected"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_orders_stats"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    keyboard.adjust(2)
    await callback.message.answer(
        f"📋 <b>Управление заказами</b>\n\nВсего: {len(orders)}\n⏳ {pending}  ✅ {confirmed}  ❌ {rejected}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_orders_pending")
async def admin_orders_pending_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    pending = [o for o in orders.values() if o.status == "pending"]
    if not pending:
        await callback.message.answer("Нет заказов в ожидании."); await callback.answer(); return
    keyboard = InlineKeyboardBuilder()
    response = f"⏳ <b>Заказы в ожидании ({len(pending)})</b>\n\n"
    for o in pending[:10]:
        user = users.get(o.user_id)
        uname = f"@{user.username}" if user else f"ID:{o.user_id}"
        response += f"<code>{o.order_id}</code>\n{uname} | {_order_card_name(o)} | {o.price}₽\n\n"
        keyboard.add(InlineKeyboardButton(text=f"#{o.order_id[-6:]}", callback_data=f"view_order_{o.order_id}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders"))
    keyboard.adjust(2)
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_orders_confirmed")
async def admin_orders_confirmed_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    confirmed = sorted([o for o in orders.values() if o.status == "confirmed"],
                       key=lambda o: o.confirmed_at or o.created_at, reverse=True)
    response = f"✅ <b>Подтверждённые ({len(confirmed)})</b>\n\n"
    for o in confirmed[:10]:
        user = users.get(o.user_id)
        uname = f"@{user.username}" if user else f"ID:{o.user_id}"
        dt = datetime.fromisoformat(o.confirmed_at or o.created_at).strftime('%d.%m %H:%M')
        response += f"{uname} | {_order_card_name(o)} | {o.price}₽ | {dt}\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders"))
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_orders_rejected")
async def admin_orders_rejected_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    rejected = sorted([o for o in orders.values() if o.status == "rejected"],
                      key=lambda o: o.confirmed_at or o.created_at, reverse=True)
    response = f"❌ <b>Отклонённые ({len(rejected)})</b>\n\n"
    for o in rejected[:10]:
        user = users.get(o.user_id)
        uname = f"@{user.username}" if user else f"ID:{o.user_id}"
        dt = datetime.fromisoformat(o.confirmed_at or o.created_at).strftime('%d.%m %H:%M')
        response += f"{uname} | {_order_card_name(o)} | {o.price}₽ | {dt}\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders"))
    await callback.message.answer(response, reply_markup=keyboard.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_orders_stats")
async def admin_orders_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    total_revenue = sum(o.price for o in orders.values() if o.status == "confirmed")
    rarity_stats = {}
    for o in orders.values():
        if o.status == "confirmed":
            c = cards.get(o.card_id)
            if c:
                rarity_stats[c.rarity] = rarity_stats.get(c.rarity, 0) + 1
    r = f"📊 <b>Статистика заказов</b>\n\nВсего: {len(orders)}\nВыручка: {total_revenue}₽\n\n"
    for rarity in ["basic","cool","legendary","vinyl figure"]:
        cnt = rarity_stats.get(rarity, 0)
        if cnt:
            r += f"{get_rarity_color(rarity)} {get_rarity_name(rarity)}: {cnt}\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders"))
    await callback.message.answer(r, reply_markup=keyboard.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("view_order_"))
async def view_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    order_id = callback.data.replace("view_order_", "")
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True); return
    o = orders[order_id]
    user = users.get(o.user_id)
    card_name = _order_card_name(o)
    status_map = {"pending": "⏳ Ожидает", "confirmed": "✅ Подтверждён", "rejected": "❌ Отклонён"}
    dt = datetime.fromisoformat(o.created_at).strftime('%d.%m.%Y %H:%M')
    gift_info = ""
    if hasattr(o, 'gift_to_user_id') and o.gift_to_user_id:
        gift_user = users.get(o.gift_to_user_id)
        gift_info = f"\n🎁 Подарок: @{gift_user.username if gift_user else o.gift_to_user_id}"
    r = (
        f"📋 <b>Заказ {order_id}</b>\n\n"
        f"👤 @{user.username if user else 'неизвестно'}\n"
        f"🎴 {card_name}\n"
        f"💰 {o.price}₽\n"
        f"📊 {status_map.get(o.status, o.status)}\n"
        f"📅 {dt}{gift_info}\n"
        f"📸 Скриншот: {'✅' if o.payment_proof else '❌'}"
    )
    keyboard = InlineKeyboardBuilder()
    if o.status == "pending":
        keyboard.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_order_{order_id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{order_id}"))
        if o.payment_proof:
            keyboard.add(InlineKeyboardButton(text="📸 Скриншот", callback_data=f"show_proof_{order_id}"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders"))
    keyboard.adjust(2)
    await callback.message.answer(r, reply_markup=keyboard.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("show_proof_"))
async def show_proof_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    order_id = callback.data.replace("show_proof_", "")
    o = orders.get(order_id)
    if not o or not o.payment_proof:
        await callback.answer("❌ Скриншот не найден", show_alert=True); return
    try:
        await bot.send_photo(callback.from_user.id, o.payment_proof,
                             caption=f"📸 Скриншот для заказа {order_id}")
        await callback.answer("📸 Скриншот отправлен в ЛС")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("confirm_order_"))
async def confirm_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    order_id = callback.data.replace("confirm_order_", "")
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True); return
    success = confirm_order(order_id, callback.from_user.id)
    if success:
        o = orders[order_id]
        user = users.get(o.user_id)
        card_name = _order_card_name(o)
        try:
            await callback.message.edit_text(
                f"✅ <b>Заказ подтверждён!</b>\n🆔 {order_id}\n👤 @{user.username if user else '?'}\n🎴 {card_name}\n💰 {o.price}₽"
            )
        except Exception:
            await callback.message.answer(f"✅ Заказ {order_id} подтверждён!")
        if user:
            try:
                await send_order_notification(order_id, user.user_id, card_name, o.price)
            except Exception as e:
                logger.error(f"Ошибка уведомления: {e}")
        await callback.answer("✅ Подтверждено!")
    else:
        await callback.answer("❌ Ошибка подтверждения", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("reject_order_"))
async def reject_order_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    order_id = callback.data.replace("reject_order_", "")
    if order_id not in orders:
        await callback.answer("❌ Заказ не найден", show_alert=True); return
    success = reject_order(order_id, callback.from_user.id)
    if success:
        o = orders[order_id]
        user = users.get(o.user_id)
        card_name = _order_card_name(o)
        try:
            await callback.message.edit_text(f"❌ <b>Заказ отклонён!</b>\n🆔 {order_id}\n🎴 {card_name}")
        except Exception:
            await callback.message.answer(f"❌ Заказ {order_id} отклонён.")
        if user:
            try:
                await bot.send_message(user.user_id,
                    f"❌ <b>Заказ отклонён.</b>\n🆔 {order_id}\n🎴 {card_name}\n\n"
                    f"Если это ошибка — напишите @prikolovwork")
            except: pass
        await callback.answer("Отклонено.")
    else:
        await callback.answer("❌ Ошибка отклонения", show_alert=True)


# ══════════════════════════════════════════
# Бан / Разбан
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_ban_user")
async def admin_ban_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("⛔ <b>Бан</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_ban_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_ban_username)
async def process_ban_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    if not user:
        await message.answer(f"❌ @{username} не найден."); await state.clear(); return
    await state.update_data(ban_username=username, ban_user_id=user.user_id)
    await message.answer(f"Причина бана для @{username}:")
    await state.set_state(AdminStates.waiting_for_ban_reason)

@router.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    await state.update_data(ban_reason=message.text)
    await message.answer("Кол-во дней бана (0 = навсегда):")
    await state.set_state(AdminStates.waiting_for_ban_days)

@router.message(AdminStates.waiting_for_ban_days)
async def process_ban_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    try:
        days = int(message.text)
    except:
        await message.answer("❌ Введите число."); return
    data = await state.get_data()
    user = users.get(data['ban_user_id'])
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    ban_user(user, data['ban_reason'], days)
    duration = "навсегда" if days == 0 else f"на {days} дней"
    await message.answer(f"✅ @{data['ban_username']} забанен {duration}.")
    try:
        await bot.send_message(user.user_id, f"⛔ Вы забанены {duration}.\nПричина: {data['ban_reason']}")
    except: pass
    await state.clear()

@router.callback_query(lambda c: c.data == "admin_unban_user")
async def admin_unban_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("✅ <b>Разбан</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_unban_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_unban_username)
async def process_unban_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user or not user.is_banned:
        await message.answer("❌ Пользователь не найден или не забанен."); await state.clear(); return
    user.is_banned = False; user.ban_reason = None; user.banned_until = None
    update_user_interaction(user)
    await message.answer(f"✅ @{user.username} разбанен!")
    try:
        await bot.send_message(user.user_id, "✅ Ваш аккаунт разблокирован!")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# Заморозка
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_freeze_user")
async def admin_freeze_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("❄️ <b>Заморозка</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_freeze_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_freeze_username)
async def process_freeze_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    username = message.text.strip().lstrip('@')
    user = get_user_by_username(username)
    if not user:
        await message.answer(f"❌ @{username} не найден."); await state.clear(); return
    await state.update_data(freeze_user_id=user.user_id, freeze_username=username)
    await message.answer("Кол-во дней заморозки (0 = навсегда):")
    await state.set_state(AdminStates.waiting_for_freeze_days)

@router.message(AdminStates.waiting_for_freeze_days)
async def process_freeze_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    try:
        days = int(message.text)
    except:
        await message.answer("❌ Введите число."); return
    data = await state.get_data()
    user = users.get(data['freeze_user_id'])
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return
    user.is_frozen = True
    if days > 0:
        user.frozen_until = (datetime.now() + timedelta(days=days)).isoformat()
        duration = f"на {days} дней"
    else:
        user.frozen_until = None
        duration = "навсегда"
    update_user_interaction(user)
    await message.answer(f"✅ @{data['freeze_username']} заморожен {duration}.")
    try:
        await bot.send_message(user.user_id, f"❄️ Ваш аккаунт заморожен {duration}.")
    except: pass
    await state.clear()

@router.callback_query(lambda c: c.data == "admin_unfreeze_user")
async def admin_unfreeze_user_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("☀️ <b>Разморозка</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_unfreeze_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_unfreeze_username)
async def process_unfreeze_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    user = get_user_by_username(message.text.strip().lstrip('@'))
    if not user or not user.is_frozen:
        await message.answer("❌ Пользователь не найден или не заморожен."); await state.clear(); return
    user.is_frozen = False; user.frozen_until = None
    update_user_interaction(user)
    await message.answer(f"✅ @{user.username} разморожен!")
    try:
        await bot.send_message(user.user_id, "☀️ Ваш аккаунт разморожен!")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# Система уровней
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_level_system")
async def admin_level_system_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    total = len(users)
    avg_level = sum(u.level for u in users.values()) / total if total else 0
    max_level = max((u.level for u in users.values()), default=0)
    status = "✅ ВКЛЮЧЕНА" if LEVEL_SETTINGS['enabled'] else "❌ ВЫКЛЮЧЕНА"
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f"🔄 {status}", callback_data="toggle_level_system"))
    keyboard.add(InlineKeyboardButton(text="📊 Статистика уровней", callback_data="level_stats"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    keyboard.adjust(1)
    await callback.message.answer(
        f"⚙️ <b>Система уровней</b>\n\nСтатус: {status}\n"
        f"Игроков: {total}\nСредний уровень: {avg_level:.1f}\nМакс: {max_level}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "toggle_level_system")
async def toggle_level_system_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    LEVEL_SETTINGS['enabled'] = not LEVEL_SETTINGS['enabled']
    status = "✅ ВКЛЮЧЕНА" if LEVEL_SETTINGS['enabled'] else "❌ ВЫКЛЮЧЕНА"
    await callback.answer(f"Система уровней: {status}", show_alert=True)
    await admin_level_system_handler(callback)

@router.callback_query(lambda c: c.data == "level_stats")
async def level_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    total = len(users)
    avg_level = sum(u.level for u in users.values()) / total if total else 0
    max_level = max((u.level for u in users.values()), default=0)
    r = f"📊 <b>Уровни</b>\n\nИгроков: {total}\nСредний: {avg_level:.1f}\nМакс: {max_level}\n\n"
    dist = {}
    for u in users.values():
        dist[u.level] = dist.get(u.level, 0) + 1
    for lv in sorted(dist.keys())[:15]:
        pct = dist[lv] / total * 100 if total else 0
        r += f"Ур.{lv}: {dist[lv]} ({pct:.1f}%)\n"
    await callback.message.answer(r)
    await callback.answer()


# ══════════════════════════════════════════
# База данных
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_database")
async def admin_database_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    try:
        await callback.message.answer_document(
            document=FSInputFile(USERS_FILE),
            caption=f"📥 <b>База данных</b>\n\nПользователей: {len(users)}"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка выгрузки: {e}")
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_update_pool")
async def admin_update_pool_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    update_card_pool()
    await callback.answer(f"✅ Пул обновлён! Записей: {len(card_pool)}", show_alert=True)

@router.callback_query(lambda c: c.data == "admin_back")
async def admin_back_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await cmd_admin(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_restart")
async def admin_restart_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    save_data()
    await callback.answer("✅ Данные сохранены!", show_alert=True)


# ══════════════════════════════════════════
# Промокоды (ИСПРАВЛЕНО)
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_create_promo")
async def admin_create_promo_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🎴 Карточка", callback_data="promo_reward_card"))
    keyboard.add(InlineKeyboardButton(text="🔄 Сброс кулдауна обменов", callback_data="promo_reward_reset_trade"))
    keyboard.add(InlineKeyboardButton(text="⚡ Сброс кулдауна карточек", callback_data="promo_reward_reset_card"))
    keyboard.add(InlineKeyboardButton(text="💎 Премиум на 3 дня", callback_data="promo_reward_premium_3d"))
    keyboard.add(InlineKeyboardButton(text="🎫 Токены", callback_data="promo_reward_tokens"))
    keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo"))
    keyboard.adjust(1)
    await callback.message.answer(
        "🎫 <b>Создание промокода</b>\n\nВыберите тип награды:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(AdminStates.waiting_for_promo_reward_type)
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_promo")
async def cancel_promo_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание промокода отменено.")
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("promo_reward_"), AdminStates.waiting_for_promo_reward_type)
async def promo_reward_type_handler(callback: types.CallbackQuery, state: FSMContext):
    reward_type = callback.data.replace("promo_reward_", "")
    await state.update_data(reward_type=reward_type)

    if reward_type == "card":
        # Показываем список карточек
        if not cards:
            await callback.answer("❌ Нет карточек в системе!", show_alert=True)
            await state.clear(); return
        cards_text = "\n".join([f"<code>{cid}</code>: {c.name} ({get_rarity_name(c.rarity)})"
                                for cid, c in list(cards.items())[:50]])
        await callback.message.answer(
            f"🎴 Доступные карточки:\n\n{cards_text}\n\nВведите ID карточки:"
        )
        await state.set_state(AdminStates.waiting_for_promo_reward_value)
    elif reward_type == "tokens":
        await callback.message.answer("🎫 Введите количество токенов:")
        await state.set_state(AdminStates.waiting_for_promo_reward_value)
    else:
        # Для reset_trade, reset_card, premium_3d — переходим сразу к ограничениям
        await state.update_data(reward_value=None)
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="⏱️ По кол-ву активаций", callback_data="promo_limit_uses"))
        keyboard.add(InlineKeyboardButton(text="⏳ По времени (минуты)", callback_data="promo_limit_time"))
        keyboard.adjust(1)
        await callback.message.answer("Выберите тип ограничения:", reply_markup=keyboard.as_markup())
        await state.set_state(AdminStates.waiting_for_promo_max_uses)
    await callback.answer()

@router.message(AdminStates.waiting_for_promo_reward_value)
async def promo_reward_value_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    data = await state.get_data()
    reward_type = data.get('reward_type')
    value = message.text.strip()
    if reward_type == "card":
        if value not in cards:
            await message.answer("❌ Карточка не найдена. Введите корректный ID:"); return
    elif reward_type == "tokens":
        try:
            amount = int(value)
            if amount <= 0: raise ValueError
        except:
            await message.answer("❌ Введите положительное число токенов:"); return
    await state.update_data(reward_value=value)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⏱️ По кол-ву активаций", callback_data="promo_limit_uses"))
    keyboard.add(InlineKeyboardButton(text="⏳ По времени (минуты)", callback_data="promo_limit_time"))
    keyboard.adjust(1)
    await message.answer("Выберите тип ограничения:", reply_markup=keyboard.as_markup())
    await state.set_state(AdminStates.waiting_for_promo_max_uses)

@router.callback_query(lambda c: c.data == "promo_limit_uses", AdminStates.waiting_for_promo_max_uses)
async def promo_limit_uses_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(limit_type="uses")
    await callback.message.answer("Введите максимальное количество активаций:")
    await state.set_state(AdminStates.waiting_for_promo_expires)
    await callback.answer()

@router.callback_query(lambda c: c.data == "promo_limit_time", AdminStates.waiting_for_promo_max_uses)
async def promo_limit_time_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(limit_type="time")
    await callback.message.answer("Введите количество минут действия промокода:")
    await state.set_state(AdminStates.waiting_for_promo_expires)
    await callback.answer()

@router.message(AdminStates.waiting_for_promo_expires)
async def promo_expires_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    try:
        value = int(message.text.strip())
        if value <= 0: raise ValueError
    except:
        await message.answer("❌ Введите положительное число."); return

    data = await state.get_data()
    limit_type = data.get('limit_type')
    reward_type = data.get('reward_type')
    reward_value = data.get('reward_value')

    if limit_type == "uses":
        max_uses = value; expires_minutes = None; expires_text = f"{value} активаций"
    else:
        max_uses = 999999; expires_minutes = value; expires_text = f"{value} минут"

    if not promo_manager:
        await message.answer("❌ Promo manager не инициализирован!"); await state.clear(); return

    promo_code = promo_manager.create_promo(reward_type, reward_value, max_uses, expires_minutes)

    reward_labels = {
        "reset_trade": "🔄 Сброс кулдауна обменов",
        "reset_card": "⚡ Сброс кулдауна карточек",
        "premium_3d": "💎 Премиум на 3 дня",
    }
    if reward_type == "card":
        c = cards.get(reward_value)
        reward_text = f"🎴 {c.name}" if c else f"Карточка {reward_value}"
    elif reward_type == "tokens":
        reward_text = f"🎫 {reward_value} токенов"
    else:
        reward_text = reward_labels.get(reward_type, reward_type)

    await message.answer(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎫 Код: <code>{promo_code}</code>\n"
        f"🎁 Награда: {reward_text}\n"
        f"⏱️ Ограничение: {expires_text}\n\n"
        f"Использование: <code>/promo {promo_code}</code>"
    )
    await state.clear()


# ══════════════════════════════════════════
# Выдача токенов (ИСПРАВЛЕНО)
# ══════════════════════════════════════════
@router.callback_query(lambda c: c.data == "admin_give_tokens")
async def admin_give_tokens_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    await callback.message.answer("🎁 <b>Выдача токенов</b>\n\nВведите @username:")
    await state.set_state(AdminStates.waiting_for_give_tokens_username)
    await callback.answer()

@router.message(AdminStates.waiting_for_give_tokens_username)
async def process_give_tokens_username(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    username = message.text.strip().lstrip('@')
    if username.lower() in ["/refresh", "отмена", "cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return
    user = get_user_by_username(username)
    if not user:
        await message.answer(f"❌ @{username} не найден. Попробуйте ещё:"); return
    await state.update_data(target_user_id=user.user_id, target_username=username)
    await message.answer(f"@{username} — баланс: {user.tokens}🎫\n\nВведите количество токенов:")
    await state.set_state(AdminStates.waiting_for_give_tokens_amount)

@router.message(AdminStates.waiting_for_give_tokens_amount)
async def process_give_tokens_amount(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: await state.clear(); return
    text = message.text.strip()
    if text.lower() in ["/refresh", "отмена", "cancel"]:
        await state.clear(); await message.answer("✅ Отменено."); return
    try:
        amount = int(text)
        if amount <= 0: raise ValueError
    except:
        await message.answer("❌ Введите положительное целое число:"); return

    data = await state.get_data()
    user = users.get(data.get('target_user_id'))
    if not user:
        await message.answer("❌ Пользователь не найден."); await state.clear(); return

    old_balance = user.tokens
    user.tokens += amount
    update_user_interaction(user)
    save_data()
    await message.answer(
        f"✅ <b>Токены выданы!</b>\n\n"
        f"👤 @{data['target_username']}\n"
        f"➕ +{amount}🎫\n"
        f"💎 Баланс: {old_balance} → {user.tokens}🎫"
    )
    try:
        await bot.send_message(user.user_id,
            f"🎁 Вам выданы токены администратором!\n\n+{amount}🎫\nНовый баланс: {user.tokens}🎫")
    except: pass
    await state.clear()


# ══════════════════════════════════════════
# addexclusive команда
# ══════════════════════════════════════════
@router.message(Command("addexclusive"))
async def add_exclusive_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа"); return
    from models import ExclusiveCard
    try:
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer("❌ Формат: <code>/addexclusive card_id copies price [days]</code>"); return
        card_id = parts[1]; total_copies = int(parts[2]); price = int(parts[3])
        if card_id not in cards:
            await message.answer(f"❌ Карточка {card_id} не найдена"); return
        end_date = None
        if len(parts) >= 5:
            end_date = (datetime.now() + timedelta(days=int(parts[4]))).isoformat()
        exclusive_cards[card_id] = ExclusiveCard(card_id=card_id, total_copies=total_copies,
                                                 price=price, end_date=end_date)
        save_data()
        await message.answer(
            f"✅ Эксклюзив добавлен!\n🎴 {cards[card_id].name}\n📦 {total_copies} копий\n💰 {price}₽"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
