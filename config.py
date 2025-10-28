"""Конфигурация бота."""

import os
from typing import Optional


class Settings:
    """Настройки бота."""
    
    def __init__(self):
        self.bot_token = "8408362344:AAHIyzDtqbxY8nEHO6iAngg7bzAHCl_AtwI"
        self.admin_id = 1447955117
        if self.admin_id:
            try:
                self.admin_id = int(self.admin_id)
            except ValueError:
                self.admin_id = None
        
        self.max_message_length = 4096
        self.history_limit = 50
        self.database_url = "sqlite:///./slang_bot.db"


# Глобальный экземпляр настроек
settings = Settings()
