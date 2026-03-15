# states.py
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_card_name = State()
    waiting_for_card_rarity = State()
    waiting_for_card_image = State()
    waiting_for_premium_username = State()
    waiting_for_cooldown_username = State()
    waiting_for_add_cooldown_username = State()
    waiting_for_reduced_cd_username = State()
    waiting_for_reduced_trade_cd_username = State()
    waiting_for_card_id_to_delete = State()
    waiting_for_ban_username = State()
    waiting_for_ban_reason = State()
    waiting_for_ban_days = State()
    waiting_for_unban_username = State()
    waiting_for_freeze_username = State()
    waiting_for_freeze_days = State()
    waiting_for_unfreeze_username = State()
    waiting_for_order_id = State()
    waiting_for_give_card_username = State()
    waiting_for_give_card_id = State()
    waiting_for_promo_reward_type = State()
    waiting_for_promo_reward_value = State()
    waiting_for_promo_max_uses = State()
    waiting_for_promo_expires = State()
    waiting_for_promo_code = State()
    waiting_for_give_tokens_username = State()
    waiting_for_give_tokens_amount = State()

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
