"""Memory Lab research and trading-support package. Paper only; agents never place orders."""
import importlib
import importlib.abc
import importlib.util
import sys


class _AppBackendAlias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Serve the legacy `app.backend.*` imports from the byte-identical copies in `lab.core`.

    Frozen research evidence pins the sha256 of files that import `app.backend.*`, so those files
    must not change. The web app was removed; this alias keeps them importable. It sits last on
    `sys.meta_path`, so a real `app` package, if present, always wins.
    """

    TARGETS = {
        "app.backend.money": "lab.core.money",
        "app.backend.strategies.c13c": "lab.core.c13c",
        "app.backend.portfolio_replay": "lab.core.portfolio_replay",
    }
    PACKAGES = {"app", "app.backend", "app.backend.strategies"}

    def find_spec(self, name, path=None, target=None):
        if name in self.TARGETS:
            return importlib.util.spec_from_loader(name, self)
        if name in self.PACKAGES:
            return importlib.util.spec_from_loader(name, self, is_package=True)
        return None

    def create_module(self, spec):
        if spec.name in self.TARGETS:
            return importlib.import_module(self.TARGETS[spec.name])
        return None

    def exec_module(self, module):
        return None


if not any(isinstance(f, _AppBackendAlias) for f in sys.meta_path):
    sys.meta_path.append(_AppBackendAlias())
