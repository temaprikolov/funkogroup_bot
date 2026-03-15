# games.py
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

@dataclass
class GameStats:
    rock_paper_scissors: Dict = field(default_factory=lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
    dice: Dict = field(default_factory=lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
    slots: Dict = field(default_factory=lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})

    def winrate(self) -> float:
        total_games = self.rock_paper_scissors['total'] + self.dice['total'] + self.slots['total']
        total_wins = self.rock_paper_scissors['wins'] + self.dice['wins'] + self.slots['wins']
        if total_games == 0:
            return 0.0
        return round((total_wins / total_games) * 100, 1)

    def total_wins(self) -> int:
        return self.rock_paper_scissors['wins'] + self.dice['wins'] + self.slots['wins']

    def total_games(self) -> int:
        return self.rock_paper_scissors['total'] + self.dice['total'] + self.slots['total']

    def get_winrate_by_game(self, game_type: str) -> float:
        stats = getattr(self, game_type)
        if stats['total'] == 0:
            return 0.0
        return round((stats['wins'] / stats['total']) * 100, 1)


class GameChallenge:
    def __init__(self, challenger_id, opponent_id, game_type, bet_type, bet_amount, card_id=None, opponent_card_id=None):
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.game_type = game_type
        self.bet_type = bet_type
        self.bet_amount = bet_amount
        self.card_id = card_id               # карта challenger'а
        self.opponent_card_id = opponent_card_id  # карта opponent'а (когда оба бетают)
        self.status = 'pending'
        self.challenger_choice = None
        self.opponent_choice = None
        self.accepted_at = None
        self.result = None
        self.winner_id = None
        self.created_at = datetime.now().isoformat()


class DailyWheel:
    """Ежедневное колесо удачи (бесплатно для всех, раз в день)."""
    PRIZES = [
        {"type": "tokens",     "weight": 50, "min": 2,  "max": 8,  "name": "🎫 Токены"},
        {"type": "tokens",     "weight": 25, "min": 9,  "max": 20, "name": "🎫 Токены (бонус)"},
        {"type": "skip_card",  "weight": 10, "min": 1,  "max": 1,  "name": "⚡ Скип карточки"},
        {"type": "skip_trade", "weight": 8,  "min": 1,  "max": 1,  "name": "⚡ Скип обмена"},
        {"type": "free_ticket","weight": 5,  "min": 1,  "max": 3,  "name": "🎟 Билет колеса"},
        {"type": "basic_card", "weight": 2,  "min": 1,  "max": 1,  "name": "⚪ Базовая карточка"},
    ]

    @staticmethod
    def spin(is_premium: bool = False) -> dict:
        """Крутим колесо. Премиум удваивает награду."""
        prizes = DailyWheel.PRIZES
        total_weight = sum(p["weight"] for p in prizes)
        rand = random.randint(1, total_weight)
        current = 0
        selected = prizes[-1]
        for prize in prizes:
            current += prize["weight"]
            if rand <= current:
                selected = prize
                break
        amount = random.randint(selected["min"], selected["max"])
        if is_premium and selected["type"] == "tokens":
            amount = amount * 2
        return {"type": selected["type"], "amount": amount, "name": selected["name"]}


class FortuneWheel:
    """Колесо фортуны на билеты (раз в 2 дня, крупные призы)."""
    def __init__(self):
        self.wheel_id = f"wheel_{int(datetime.now().timestamp())}"
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(days=2)
        self.participants: Dict[int, int] = {}
        self.prizes_pool = {
            'skip_trade': {'weight': 30, 'min': 1, 'max': 3, 'name': '⚡ Скип обмена'},
            'skip_card':  {'weight': 30, 'min': 1, 'max': 3, 'name': '⚡ Скип карточки'},
            'tokens':     {'weight': 25, 'min': 10,'max': 100,'name': '🎫 Токены'},
            'cool_card':  {'weight': 10, 'min': 1, 'max': 1, 'name': '🔵 Крутая карточка'},
            'legendary_card': {'weight': 4,'min': 1,'max': 1, 'name': '🟡 Легендарная карточка'},
            'vinyl_card': {'weight': 1,  'min': 1, 'max': 1, 'name': '🟣 Виниловая фигурка'},
        }

    def add_tickets(self, user_id: int, tickets: int):
        self.participants[user_id] = self.participants.get(user_id, 0) + tickets

    def get_total_tickets(self) -> int:
        return sum(self.participants.values())

    def get_participants_count(self) -> int:
        return len(self.participants)

    def draw_winners(self, all_cards: Dict) -> Dict[int, List[Tuple]]:
        results = {}
        total_tickets = self.get_total_tickets()
        if total_tickets == 0:
            return results
        ticket_pool = []
        for user_id, tickets in self.participants.items():
            ticket_pool.extend([user_id] * tickets)
        num_prizes = max(1, total_tickets // 5)
        for _ in range(num_prizes):
            if not ticket_pool:
                break
            winner_id = random.choice(ticket_pool)
            prize_type = self._select_prize()
            prize_info = self.prizes_pool[prize_type]
            prize_amount = random.randint(prize_info['min'], prize_info['max'])
            card_id = None
            if prize_type in ['cool_card', 'legendary_card', 'vinyl_card']:
                rarity_map = {'cool_card': 'cool', 'legendary_card': 'legendary', 'vinyl_card': 'vinyl figure'}
                possible_cards = [cid for cid, c in all_cards.items()
                                  if c.rarity == rarity_map.get(prize_type, '')]
                if possible_cards:
                    card_id = random.choice(possible_cards)
            results.setdefault(winner_id, []).append(
                (prize_type, prize_amount, prize_info['name'], card_id)
            )
            for _ in range(min(prize_amount, ticket_pool.count(winner_id))):
                if winner_id in ticket_pool:
                    ticket_pool.remove(winner_id)
        return results

    def _select_prize(self) -> str:
        total_weight = sum(p['weight'] for p in self.prizes_pool.values())
        rand = random.randint(1, total_weight)
        current = 0
        for prize_type, prize_data in self.prizes_pool.items():
            current += prize_data['weight']
            if rand <= current:
                return prize_type
        return 'tokens'


def determine_rps_winner(choice1: str, choice2: str) -> int:
    """Возвращает 0 = ничья, 1 = choice1 выигрывает, 2 = choice2 выигрывает."""
    if choice1 == choice2:
        return 0
    wins = {'rock': 'scissors', 'scissors': 'paper', 'paper': 'rock'}
    if wins.get(choice1) == choice2:
        return 1
    return 2


def play_slots() -> Tuple[bool, List[str]]:
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    result = [random.choice(symbols) for _ in range(3)]
    win = result[0] == result[1] == result[2]
    return win, result
