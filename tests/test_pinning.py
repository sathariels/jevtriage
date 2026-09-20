from __future__ import annotations

import pytest

from jevtriage.pinning import (
    ModelIdentityError,
    UnpinnedModelError,
    is_unpinned,
    require_pinned,
    require_response_identity,
)


def test_rejects_empty_and_whitespace() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        require_pinned("")
    with pytest.raises(ValueError, match="nonempty"):
        require_pinned("   ")


@pytest.mark.parametrize(
    "name",
    ["jev-latest", "jev-preview", "JEV-LATEST", "custom-latest", "foo-preview-bar"],
)
def test_rejects_floating_aliases(name: str) -> None:
    assert is_unpinned(name)
    with pytest.raises(UnpinnedModelError):
        require_pinned(name)


def test_accepts_catalog_pin() -> None:
    assert require_pinned("jev-1.13.0") == "jev-1.13.0"


def test_allow_unpinned_opt_in() -> None:
    assert require_pinned("jev-latest", allow_unpinned=True) == "jev-latest"


def test_response_identity_exact() -> None:
    assert require_response_identity("jev-1.13.0", "jev-1.13.0") == "jev-1.13.0"
    with pytest.raises(ModelIdentityError):
        require_response_identity("jev-1.14.0", "jev-1.13.0")
    with pytest.raises(ModelIdentityError):
        require_response_identity(None, "jev-1.13.0")


def test_opted_in_alias_may_resolve() -> None:
    assert (
        require_response_identity("jev-1.13.0", "jev-latest", allow_unpinned=True)
        == "jev-1.13.0"
    )
    with pytest.raises(ModelIdentityError):
        require_response_identity("jev-preview", "jev-latest", allow_unpinned=True)
