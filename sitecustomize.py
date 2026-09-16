from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys


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


# The project intentionally uses long-polling for every representative bot.
# Some bot tokens may still have a Telegram webhook left over from an older
# installation. Remove it immediately before polling so one stale webhook
# cannot permanently disable that representative's update loop. Pending
# updates are preserved.
try:
    from telethon import TelegramClient

    _original_run_until_disconnected = TelegramClient.run_until_disconnected

    async def _run_without_stale_webhook(self):
        try:
            await self._request("deleteWebhook", {"drop_pending_updates": False})
        except Exception:
            # Do not prevent startup when Telegram is temporarily unavailable;
            # the normal polling loop retains its existing retry behavior.
            pass
        return await _original_run_until_disconnected(self)

    TelegramClient.run_until_disconnected = _run_without_stale_webhook
except Exception:
    pass
