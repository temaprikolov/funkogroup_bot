# promo.py
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
from pathlib import Path

class PromoCode:
    def __init__(self, code: str, reward_type: str, reward_value: str = None, max_uses: int = 1, expires_at: datetime = None):
        self.code = code
        self.reward_type = reward_type
        self.reward_value = reward_value
        self.max_uses = max_uses
        self.current_uses = 0
        self.created_at = datetime.now()
        self.expires_at = expires_at
        self.is_active = True

    def to_dict(self):
        return {
            'code': self.code,
            'reward_type': self.reward_type,
            'reward_value': self.reward_value,
            'max_uses': self.max_uses,
            'current_uses': self.current_uses,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active
        }

    @classmethod
    def from_dict(cls, data):
        promo = cls(
            code=data['code'],
            reward_type=data['reward_type'],
            reward_value=data.get('reward_value'),
            max_uses=data['max_uses']
        )
        promo.current_uses = data['current_uses']
        promo.created_at = datetime.fromisoformat(data['created_at'])
        promo.expires_at = datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        promo.is_active = data['is_active']
        return promo

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True

    def use(self) -> bool:
        if self.is_valid():
            self.current_uses += 1
            if self.max_uses > 0 and self.current_uses >= self.max_uses:
                self.is_active = False
            return True
        return False

def generate_promo_code(length: int = 8) -> str:
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

class PromoCodeManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.promos: Dict[str, PromoCode] = {}
        self.used_by_users: Dict[str, List[int]] = {}
        self.load()

    def load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.promos = {code: PromoCode.from_dict(p) for code, p in data.get('promos', {}).items()}
                    self.used_by_users = data.get('used_by_users', {})
            except:
                pass

    def save(self):
        data = {
            'promos': {code: p.to_dict() for code, p in self.promos.items()},
            'used_by_users': self.used_by_users
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_promo(self, reward_type: str, reward_value: str = None, max_uses: int = 1, expires_minutes: int = None) -> str:
        code = generate_promo_code()
        expires_at = datetime.now() + timedelta(minutes=expires_minutes) if expires_minutes else None
        promo = PromoCode(code, reward_type, reward_value, max_uses, expires_at)
        self.promos[code] = promo
        self.save()
        return code

    def use_promo(self, code: str, user_id: int) -> Optional[PromoCode]:
        code = code.upper().strip()
        promo = self.promos.get(code)
        if not promo or not promo.is_valid():
            return None
        if user_id in self.used_by_users.get(code, []):
            return None
        if promo.use():
            if code not in self.used_by_users:
                self.used_by_users[code] = []
            self.used_by_users[code].append(user_id)
            self.save()
            return promo
        return None
