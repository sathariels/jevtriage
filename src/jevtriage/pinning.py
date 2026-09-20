"""Fail-closed model pinning.

Floating aliases (`jev-latest`, `jev-preview`, or any name containing
`latest` or `preview`) are rejected in production mode. Empty names are
never pins. A documented TypeSafe catalog pin as of 2026-09-19 is
`jev-1.13.0`.
"""

from __future__ import annotations

from typing import Any

FLOATING_ALIASES = frozenset({"jev-latest", "jev-preview"})


class UnpinnedModelError(ValueError):
    """Raised when a floating model name is used without an explicit opt-in."""


class ModelIdentityError(ValueError):
    """Raised when a response model does not match the requested pin."""


def is_unpinned(model: str) -> bool:
    name = model.strip().lower()
    if not name:
        raise ValueError("model name must be a nonempty string")
    if name in FLOATING_ALIASES:
        return True
    return "latest" in name or "preview" in name


def require_pinned(model: str, *, allow_unpinned: bool = False) -> str:
    pinned = model.strip()
    if not pinned:
        raise ValueError("model name must be a nonempty string")
    if is_unpinned(pinned) and not allow_unpinned:
        raise UnpinnedModelError(
            f"{pinned!r} is an unpinned floating model; pass an explicit "
            "version (for example jev-1.13.0) or set allow_unpinned=True"
        )
    return pinned


def require_response_identity(
    response_model: Any, requested: str, *, allow_unpinned: bool = False
) -> str:
    if response_model is None:
        raise ModelIdentityError(
            f"response model is null; expected requested pin {requested!r}"
        )
    if not isinstance(response_model, str) or not response_model.strip():
        raise ModelIdentityError(
            f"response model {response_model!r} is not a nonempty string; "
            f"expected requested pin {requested!r}"
        )
    actual = response_model.strip()
    if allow_unpinned and is_unpinned(requested):
        if not is_unpinned(actual):
            return actual
        raise ModelIdentityError(
            f"response model {actual!r} is a floating alias; expected a concrete "
            f"resolved model for requested pin {requested!r}"
        )
    if actual != requested:
        raise ModelIdentityError(
            f"response model {actual!r} does not match requested pin {requested!r}"
        )
    return actual
