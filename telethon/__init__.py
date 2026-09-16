from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# NOTE: keep the existing Telethon-compatible facade implementation below.
# The document upload method is added to TelegramClient so application code
# can send raw subscription/config files through Telegram Bot API.
