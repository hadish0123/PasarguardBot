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


# Patch My Services directly before the application imports its handlers.
# This is intentionally eager instead of relying only on an import hook: the
# service module may be imported indirectly by another startup module before
# the normal finder gets a chance to intercept it.
try:
    from app.telegram.representative import user_services as _user_services
    from app.telegram.representative.config_delivery import deliver as _deliver_configs

    _user_services._send_credentials = _deliver_configs
    logger.info("real Xray share-link delivery enabled for representative My Services")
except Exception:
    logger.exception("failed to enable real Xray share-link delivery patch")


# Keep the import hook as a fallback for environments that lazy-load the
# representative services module after startup.
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


# The project intentionally uses long-polling for every representative bot.
# Some bot tokens may still have a Telegram webhook left over from an older
# installation. Remove it immediately before polling so one stale webhook
# cannot permanently disable that representative's update loop. Pending
# updates are preserved.
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
