"""Typed System One boundary. Auth is TYPESAFE_API_KEY only."""

from __future__ import annotations

import os
from typing import Any

from jevtriage.answers import TriageResult, adapt_response
from jevtriage.pinning import require_pinned, require_response_identity
from jevtriage.questions import triage_questions

AUTH_ENV = "TYPESAFE_API_KEY"
MODEL_ENV = "TYPESAFE_DEFAULT_MODEL"
BASE_URL_ENV = "TYPESAFE_BASE_URL"


class ConfigError(RuntimeError):
    """Missing key, missing pin, or other local configuration failure."""


class ApiError(RuntimeError):
    """TypeSafe call failed or returned an unusable official response."""


class JevClient:
    """Production wrapper around `typesafe_sdk.TypeSafeClient`."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        allow_unpinned: bool = False,
        base_url: str | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.model = require_pinned(model, allow_unpinned=allow_unpinned)
        self.allow_unpinned = allow_unpinned
        self.api_key = api_key if api_key is not None else os.environ.get(AUTH_ENV)
        self.base_url = base_url if base_url is not None else os.environ.get(BASE_URL_ENV)
        self._sdk_client = sdk_client

    def system_one(self, state: Any, *, model: str | None = None) -> TriageResult:
        pinned = require_pinned(model or self.model, allow_unpinned=self.allow_unpinned)
        sdk = self._sdk_client if self._sdk_client is not None else self._open_sdk(pinned)
        owns = self._sdk_client is None
        try:
            raw = sdk.system_one(
                state=state,
                questions=triage_questions(),
                model=pinned,
            )
        except (ConfigError, ApiError):
            raise
        except Exception as exc:  # SDK / HTTP failures
            raise ApiError(f"TypeSafe system_one failed: {exc}") from exc
        finally:
            if owns and hasattr(sdk, "close"):
                sdk.close()

        try:
            truncated = bool(
                isinstance(state, dict) and (
                    state.get("diff_truncated")
                    or state.get("files_truncated")
                    or state.get("jevtriage_notes")
                )
            )
            result = adapt_response(raw, truncated=truncated)
            require_response_identity(
                result.model, pinned, allow_unpinned=self.allow_unpinned
            )
        except Exception as exc:
            raise ApiError(f"unusable TypeSafe response: {exc}") from exc
        return result

    def _open_sdk(self, model: str) -> Any:
        if not self.api_key:
            raise ConfigError(
                f"{AUTH_ENV} is not set and no api_key= was passed to JevClient"
            )
        from typesafe_sdk import TypeSafeClient

        kwargs: dict[str, Any] = {"api_key": self.api_key, "model": model}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return TypeSafeClient(**kwargs)


def resolve_model(
    explicit: str | None,
    *,
    default_env: str | None = None,
    allow_unpinned: bool = False,
) -> str:
    """Resolve `--model` then `TYPESAFE_DEFAULT_MODEL`. Empty is not a pin."""
    candidate = (explicit or "").strip() or (default_env if default_env is not None else os.environ.get(MODEL_ENV, "")).strip()
    if not candidate:
        raise ConfigError(
            "model pin required: pass --model / the Action `model` input, "
            f"or set {MODEL_ENV} (for example jev-1.13.0)"
        )
    return require_pinned(candidate, allow_unpinned=allow_unpinned)
