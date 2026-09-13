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
