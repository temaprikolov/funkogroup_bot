# states.py — Состояния FSM для бота
from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Рассылка
    waiting_for_broadcast = State()
    
    # Карточки
    waiting_for_card_name = State()
    waiting_for_card_rarity = State()
    waiting_for_card_image = State()
    waiting_for_card_id_to_delete = State()
    waiting_for_weight_value = State()
    
    # Премиум
    waiting_for_premium_username = State()
    
    # Кулдауны
    waiting_for_cooldown_username = State()
    waiting_for_add_cooldown_username = State()
    waiting_for_reduced_cd_username = State()
    waiting_for_reduced_trade_cd_username = State()
    
    # Бан / Разбан
    waiting_for_ban_username = State()
    waiting_for_ban_reason = State()
    waiting_for_ban_days = State()
    waiting_for_unban_username = State()
    
    # Заморозка / Разморозка
    waiting_for_freeze_username = State()
    waiting_for_freeze_days = State()
    waiting_for_unfreeze_username = State()
    
    # Заказы
    waiting_for_order_id = State()
    
    # Выдача карточки
    waiting_for_give_card_username = State()
    waiting_for_give_card_id = State()
    
    # Промокоды
    waiting_for_promo_reward_type = State()
    waiting_for_promo_reward_value = State()
    waiting_for_promo_max_uses = State()
    waiting_for_promo_expires = State()
    waiting_for_promo_code = State()
    
    # Выдача токенов
    waiting_for_give_tokens_username = State()
    waiting_for_give_tokens_amount = State()
    
    # Поиск пользователя
    waiting_for_search_user = State()
    
    # Установка уровня
    waiting_for_set_level = State()
    
    # Массовая выдача
    waiting_for_mass_card_id = State()
    
    # Чёрный список слов
    waiting_for_bad_word_add = State()
    waiting_for_bad_word_remove = State()
    
    # Шаблоны
    waiting_for_template_name = State()
    waiting_for_template_text = State()
    waiting_for_template_remove = State()
    
    # Планировщик
    waiting_for_scheduled_task = State()
    waiting_for_schedule_delete = State()
    
    # Ивенты
    waiting_for_happy_hour_time = State()
    waiting_for_weekend_discount = State()
    
    # Квесты
    waiting_for_quest_name = State()
    waiting_for_quest_goal = State()
    waiting_for_quest_reward = State()
    
    # Достижения
    waiting_for_achievement_name = State()
    waiting_for_achievement_condition = State()
    
    # A/B тесты
    waiting_for_ab_test_name = State()
    waiting_for_ab_test_prices = State()
    
    # Опросы
    waiting_for_poll_question = State()
    waiting_for_poll_options = State()
    
    # Кастомные тексты
    waiting_for_custom_text_key = State()
    waiting_for_custom_text_value = State()
    
    # Мини-игры
    waiting_for_minigame_config = State()


class TradeStates(StatesGroup):
    selecting_my_cards = State()
    selecting_partner = State()
    confirming_trade = State()


class OrderStates(StatesGroup):
    waiting_for_payment_proof = State()


class GameStates(StatesGroup):
    choosing_bet_type = State()
    choosing_opponent = State()
    choosing_bet_card = State()
    choosing_bet_token_amount = State()
    waiting_for_game_choice = State()
    gifting_card_select = State()
    gifting_card_username = State()


class CraftStates(StatesGroup):
    choosing_recipe = State()
    selecting_cards = State()
    confirming_craft = State()


class ShopStates(StatesGroup):
    choosing_lootbox = State()
    entering_gift_username = State()


class WheelBuyState(StatesGroup):
    entering_ticket_amount = State()


class UserStates(StatesGroup):
    waiting_for_trade_partner = State()
    waiting_for_trade_cards = State()
    waiting_for_trade_confirm = State()
    waiting_for_gift_username = State()
    waiting_for_gift_card = State()
    waiting_for_promo_code = State()
    waiting_for_payment_proof = State()
    waiting_for_auction_bid = State()
    waiting_for_lootbox_open = State()
    waiting_for_wheel_spin = State()
    waiting_for_secret_shop = State()
