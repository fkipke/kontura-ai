"""Tests fuer Password-Hashing."""

import pytest

from kontura.core.security import hash_password, verify_password


def test_hash_password_returns_non_empty_string() -> None:
    h = hash_password("supersecret")
    assert isinstance(h, str)
    assert len(h) > 20


def test_hash_password_creates_different_hashes_per_call() -> None:
    """bcrypt nutzt zufaellige Salts -> gleicher Input, andere Hashes."""
    h1 = hash_password("supersecret")
    h2 = hash_password("supersecret")
    assert h1 != h2


def test_verify_password_accepts_correct_password() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True


def test_verify_password_rejects_wrong_password() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter3", h) is False


def test_verify_password_rejects_empty_inputs() -> None:
    h = hash_password("hunter2")
    assert verify_password("", h) is False
    assert verify_password("hunter2", "") is False


def test_verify_password_handles_invalid_hash_gracefully() -> None:
    """Korrupter Hash darf nicht crashen, sondern False liefern."""
    assert verify_password("hunter2", "not-a-real-bcrypt-hash") is False


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError, match="leer"):
        hash_password("")
