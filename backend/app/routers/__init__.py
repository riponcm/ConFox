"""Feature routers. Each feature adds one module here that defines `router = APIRouter(...)`; main.py includes
every such module automatically, so features never need to edit main.py."""

import importlib
import pkgutil

from fastapi import APIRouter, FastAPI


def include_all(app: FastAPI) -> list[str]:
    names = []
    for mod in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{mod.name}")
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            app.include_router(router)
            names.append(mod.name)
    return names
