from __future__ import annotations

import importlib.abc
import importlib.machinery
import logging
import sys

logger = logging.getLogger("pasarguardbot.sitecustomize")


class _WebAdminFinder(importlib.abc.MetaPathFinder):
    _done = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "app.web_admin" or self._done:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        original = spec.loader
        finder = self

        class _Loader(importlib.abc.Loader):
            def create_module(self, spec):
                if hasattr(original, "create_module"):
                    return original.create_module(spec)
                return None

            def exec_module(self, module):
                original.exec_module(module)
                from app.web_admin_ui import apply
                apply(module)
                finder._done = True

        spec.loader = _Loader()
        return spec


if not any(isinstance(x, _WebAdminFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _WebAdminFinder())


try:
    from app.telegram.representative import user_services as _user_services
    from app.telegram.representative.config_delivery import deliver as _deliver_configs

    _user_services._send_credentials = _deliver_configs
    logger.info("real Xray share-link delivery enabled for representative My Services")
except Exception:
    logger.exception("failed to enable real Xray share-link delivery patch")


class _UserServicesFinder(importlib.abc.MetaPathFinder):
    _done = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "app.telegram.representative.user_services" or self._done:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        original = spec.loader
        finder = self

        class _Loader(importlib.abc.Loader):
            def create_module(self, spec):
                if hasattr(original, "create_module"):
                    return original.create_module(spec)
                return None

            def exec_module(self, module):
                original.exec_module(module)
                from app.telegram.representative.config_delivery import deliver
                module._send_credentials = deliver
                finder._done = True

        spec.loader = _Loader()
        return spec


if not any(isinstance(x, _UserServicesFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _UserServicesFinder())


# Keep the user's /start message outside the bot-message cleanup set.
# The normal /start handler only intends to remove messages sent by the bot.
# This guard makes that invariant explicit before cleanup runs.
try:
    from app.telegram.representative import runtime as _representative_runtime

    _original_start = _representative_runtime.RepresentativeRuntime._start

    async def _start_preserving_user_message(self, event):
        try:
            incoming_id = getattr(getattr(event, "message", None), "id", None)
            tracked = getattr(self.client, "_bot_message_ids", None)
            if incoming_id is not None and tracked is not None and event.chat_id is not None:
                tracked.setdefault(int(event.chat_id), set()).discard(int(incoming_id))
        except Exception:
            logger.debug("Could not protect incoming /start message", exc_info=True)
        return await _original_start(self, event)

    _representative_runtime.RepresentativeRuntime._start = _start_preserving_user_message
    logger.info("incoming /start message protection enabled")
except Exception:
    logger.exception("failed to install /start message protection")


try:
    from telethon import TelegramClient

    _original_send_message = TelegramClient.send_message
    _original_edit_message = TelegramClient.edit_message

    async def _safe_send_message(self, entity, message="", *, buttons=None, **kwargs):
        if kwargs.get("parse_mode") is None:
            kwargs.pop("parse_mode", None)
        return await _original_send_message(self, entity, message, buttons=buttons, **kwargs)

    async def _safe_edit_message(self, entity, message_id, text, *, buttons=None, **kwargs):
        if kwargs.get("parse_mode") is None:
            kwargs.pop("parse_mode", None)
        return await _original_edit_message(self, entity, message_id, text, buttons=buttons, **kwargs)

    TelegramClient.send_message = _safe_send_message
    TelegramClient.edit_message = _safe_edit_message

    _original_run_until_disconnected = TelegramClient.run_until_disconnected

    async def _run_without_stale_webhook(self):
        try:
            await self._request("deleteWebhook", {"drop_pending_updates": False})
        except Exception:
            pass
        return await _original_run_until_disconnected(self)

    TelegramClient.run_until_disconnected = _run_without_stale_webhook
except Exception:
    logger.exception("failed to install Telegram runtime safety patches")
